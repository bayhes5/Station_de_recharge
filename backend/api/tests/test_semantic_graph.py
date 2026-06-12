from datetime import timedelta

import pytest
from django.utils import timezone
from django.test import override_settings

pytest.importorskip("rdflib")

from api.models import (  # noqa: E402
    Alerte,
    Capteur,
    CapteurData,
    Device,
    DeviceStatus,
    DeviceType,
    EmplacementStatus,
    Reservation,
    ReservationAuthChoice,
    ReservationStatus,
    Session,
    Technicien,
    TechnicienStation,
)
from api.services.semantic_graph import build_semantic_graph, serialize_semantic_graph  # noqa: E402


def _create_semantic_fixture(user, station, borne, emplacements):
    emplacement = emplacements[0]
    emplacement.statut = EmplacementStatus.OCCUPIED
    emplacement.save(update_fields=["statut"])

    device = Device.objects.create(
        emplacement=emplacement,
        type_device=DeviceType.ESP32,
        firmware_version="0.9.0",
        expected_firmware_version="1.0.0",
        firmware_update_status="update_required",
        ip_address="192.168.1.50",
        hardware_mac="AA:BB:CC:DD:EE:FF",
        slot_id="slot1",
        last_seen=timezone.now(),
        status=DeviceStatus.CHARGING,
    )
    capteur = Capteur.objects.create(device=device, type="temperature", unite="C")
    measure = CapteurData.objects.create(capteur=capteur, valeur=72.5)

    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacement,
        auth_choice=ReservationAuthChoice.QR,
        date_debut=timezone.now() - timedelta(minutes=10),
        date_fin=timezone.now() + timedelta(minutes=50),
        statut=ReservationStatus.ACTIVE,
        reference_code="SEMANTIC1",
    )
    Session.objects.create(
        reservation=reservation,
        emplacement=emplacement,
        start_time=timezone.now(),
        charge_state="charging",
    )

    technicien = Technicien.objects.create(
        nom="Technicien Centre",
        email="tech-centre@example.com",
        telephone="0600000000",
    )
    TechnicienStation.objects.create(technicien=technicien, station=station, role="referent")
    Alerte.objects.create(
        data=measure,
        type="temperature_high",
        message="Temperature superieure au seuil.",
        niveau_severite="critical",
        status="active",
        assigned_technician=technicien,
    )


def test_semantic_graph_exports_operational_data_without_private_contacts(
    user, station, borne, emplacements
):
    _create_semantic_fixture(user, station, borne, emplacements)

    graph = build_semantic_graph()
    turtle = serialize_semantic_graph(graph, "turtle")

    assert "Station Centre" in turtle
    assert "Borne 1" in turtle
    assert "firmwareStatus" in turtle
    assert "latestObservation" in turtle
    assert "ChargingSession" in turtle
    assert "Technicien Centre" in turtle
    assert "tech-centre@example.com" not in turtle
    assert "0600000000" not in turtle
    assert "user@example.com" not in turtle


@override_settings(SEMANTIC_DEV_ENDPOINTS_ENABLED=False)
def test_semantic_endpoint_is_disabled_by_default(admin_client):
    response = admin_client.get("/api/semantic/graph/")

    assert response.status_code == 404


@override_settings(SEMANTIC_DEV_ENDPOINTS_ENABLED=True)
def test_semantic_sparql_endpoint_returns_station_rows(
    admin_client, user, station, borne, emplacements
):
    _create_semantic_fixture(user, station, borne, emplacements)

    response = admin_client.post(
        "/api/semantic/sparql/",
        data={
            "query": """
                PREFIX station: <https://station-recharge.local/ontology#>

                SELECT ?stationName
                WHERE {
                  ?station a station:ChargingStation ;
                           station:name ?stationName .
                }
            """
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["head"]["vars"] == ["stationName"]
    assert response.data["results"][0]["stationName"]["value"] == "Station Centre"


@override_settings(SEMANTIC_DEV_ENDPOINTS_ENABLED=True)
def test_semantic_network_endpoint_returns_visualization_graph(
    admin_client, user, station, borne, emplacements
):
    _create_semantic_fixture(user, station, borne, emplacements)

    response = admin_client.get("/api/semantic/network/")

    assert response.status_code == 200
    nodes = response.data["nodes"]
    edges = response.data["edges"]
    node_types = {node["type"] for node in nodes}

    assert {"station", "borne", "emplacement", "device", "sensor", "session", "alert", "technician"}.issubset(
        node_types
    )
    assert any(edge["label"] == "contient" for edge in edges)
    assert any(edge["label"] == "mesure" for edge in edges)
    assert "tech-centre@example.com" not in str(response.data)
