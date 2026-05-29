import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import (
    CapteurData,
    ChargeSessionState,
    Device,
    DeviceCommandLog,
    DeviceStatus,
    DeviceType,
    Reservation,
    Session,
    SessionTelemetry,
)
from api.tasks import process_mqtt_message


@pytest.fixture(autouse=True)
def clear_mobile_session_cache():
    """Clear cached mobile sessions before each end-to-end scenario."""
    cache.clear()


def create_slot_devices(emplacements):
    """Create one ESP32 device for every demo emplacement."""
    return [
        Device.objects.create(
            emplacement=emplacement,
            type_device=DeviceType.ESP32,
            firmware_version="e2e-test",
            mac_address=f"slot{index}",
            status=DeviceStatus.PROVISIONED,
        )
        for index, emplacement in enumerate(emplacements, start=1)
    ]


def mqtt_payload(**overrides):
    """Build a realistic ESP32 telemetry payload for the active session."""
    payload = {
        "state": "charging",
        "current": 1.2,
        "voltage": 41.5,
        "power": 49.8,
        "energy_kwh": 0.02,
        "temperature": 31.0,
        "humidity": 45.0,
        "door": True,
        "cable": True,
        "timestamp": timezone.now().isoformat(),
    }
    payload.update(overrides)
    return json.dumps(payload)


@pytest.mark.django_db
def test_qr_mobile_kiosk_charge_session_end_to_end(
    authenticated_client,
    api_client,
    user,
    station,
    borne,
    emplacements,
):
    """Validate the full QR mobile kiosk charge flow up to Grafana data tables."""
    borne.mqtt_prefix = "station-centre/borne-1"
    borne.save(update_fields=["mqtt_prefix"])
    create_slot_devices(emplacements)
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="E2EQR1",
        auth_choice="qr",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=55),
        statut="confirmee",
    )

    create_mobile_response = api_client.post(
        reverse("api-terminal-mobile-session-create"),
        {
            "station_id": str(station.id_station),
            "borne_id": str(borne.id_borne),
            "frontend_origin": "http://10.42.0.15:5173",
        },
        format="json",
    )

    assert create_mobile_response.status_code == status.HTTP_201_CREATED
    token = create_mobile_response.data["mobile_session"]["token"]
    assert create_mobile_response.data["mobile_session"]["status"] == "pending"
    assert create_mobile_response.data["url"] == f"http://10.42.0.15:5173/mobile-session.html?token={token}"

    mobile_detail_response = authenticated_client.get(
        reverse("api-mobile-session-detail", kwargs={"token": token})
    )

    assert mobile_detail_response.status_code == status.HTTP_200_OK
    available_reservations = mobile_detail_response.data["reservations"]
    assert len(available_reservations) == 1
    assert available_reservations[0]["reference_code"] == reservation.reference_code
    assert available_reservations[0]["compatible_terminal"] is True

    authorize_response = authenticated_client.post(
        reverse("api-mobile-session-authorize", kwargs={"token": token}),
        {"reservation_id": str(reservation.id_reservation)},
        format="json",
    )

    assert authorize_response.status_code == status.HTTP_200_OK
    assert authorize_response.data["mobile_session"]["status"] == "authorized"

    terminal_status_response = api_client.post(
        reverse("api-terminal-mobile-session-status-body"),
        {
            "token": token,
            "station_id": str(station.id_station),
            "borne_id": str(borne.id_borne),
        },
        format="json",
    )

    assert terminal_status_response.status_code == status.HTTP_200_OK
    assert terminal_status_response.data["mobile_session"]["status"] == "authorized"

    consume_response = api_client.post(
        reverse("api-terminal-mobile-session-consume-body"),
        {
            "token": token,
            "station_id": str(station.id_station),
            "borne_id": str(borne.id_borne),
        },
        format="json",
    )

    assert consume_response.status_code == status.HTTP_200_OK
    assert consume_response.data["session_created"] is True
    assert consume_response.data["mobile_session"]["status"] == "consumed"
    assert consume_response.data["session"]["slot_id"] == "slot1"
    assert consume_response.data["session"]["mqtt_prefix"] == "station-centre/borne-1"
    assert consume_response.data["session"]["emplacement"] == 1
    mqtt_prefix = consume_response.data["session"]["mqtt_prefix"]

    session = Session.objects.get(reservation=reservation)
    reservation.refresh_from_db()
    assert reservation.statut == "active"
    assert session.end_time is None
    assert session.charge_state == ChargeSessionState.ACCESS_VALIDATED

    unlock_ack = process_mqtt_message(
        f"station/{mqtt_prefix}/slot1/ack",
        json.dumps(
            {
                "command_id": "cmd-unlock-e2e",
                "action": "UNLOCK",
                "status": "unlocked",
                "message": "Boîtier déverrouillé.",
                "session_id": str(session.id_session),
                "source": "raspberry",
            }
        ),
    )

    assert unlock_ack["message_type"] == "ack"
    assert unlock_ack["topic_prefix"] == mqtt_prefix
    assert unlock_ack["command_status"] == "unlocked"
    session.refresh_from_db()
    assert session.charge_state == ChargeSessionState.WAITING_PLUG

    start_ack = process_mqtt_message(
        f"station/{mqtt_prefix}/slot1/ack",
        json.dumps(
            {
                "command_id": "cmd-start-e2e",
                "action": "START",
                "status": "accepted",
                "message": "Emplacement réservé.",
                "session_id": str(session.id_session),
                "source": "raspberry",
            }
        ),
    )

    assert start_ack["message_type"] == "ack"
    assert start_ack["topic_prefix"] == mqtt_prefix
    assert start_ack["command_status"] == "accepted"
    session.refresh_from_db()
    assert session.charge_state == ChargeSessionState.WAITING_PLUG

    for index in range(3):
        telemetry_result = process_mqtt_message(
            f"station/{mqtt_prefix}/slot1/telemetry",
            mqtt_payload(
                session_id=str(session.id_session),
                energy_kwh=0.02 + index * 0.01,
            ),
        )
        assert telemetry_result["topic_prefix"] == mqtt_prefix
        assert telemetry_result["session_telemetry_created"] is True

    assert SessionTelemetry.objects.filter(session=session).count() == 3
    session.refresh_from_db()
    assert session.charge_state == ChargeSessionState.CHARGING
    assert set(
        CapteurData.objects.values_list("capteur__device__mac_address", flat=True)
    ) == {"slot1"}
    assert not CapteurData.objects.filter(
        capteur__device__mac_address__in=["slot2", "slot3"]
    ).exists()

    stop_ack = process_mqtt_message(
        f"station/{mqtt_prefix}/slot1/ack",
        json.dumps(
            {
                "command_id": "cmd-stop-e2e",
                "action": "STOP",
                "status": "stopped",
                "message": "Charge arrêtée.",
                "session_id": str(session.id_session),
                "source": "raspberry",
            }
        ),
    )

    assert stop_ack["message_type"] == "ack"
    assert stop_ack["topic_prefix"] == mqtt_prefix
    assert stop_ack["command_status"] == "stopped"
    session.refresh_from_db()
    assert session.charge_state == ChargeSessionState.STOPPING

    stop_response = api_client.post(
        reverse("api-terminal-session-stop"),
        {
            "session_id": str(session.id_session),
            "station_id": str(station.id_station),
            "borne_id": str(borne.id_borne),
        },
        format="json",
    )

    assert stop_response.status_code == status.HTTP_200_OK
    assert stop_response.data["session_closed"] is True
    session.refresh_from_db()
    reservation.refresh_from_db()
    assert session.end_time is not None
    assert session.charge_state == ChargeSessionState.STOPPED
    assert reservation.statut == "terminee"
    assert Session.objects.filter(end_time__isnull=True).count() == 0

    process_mqtt_message(
        f"station/{mqtt_prefix}/slot1/status",
        json.dumps(
            {
                "state": "stopped",
                "session_id": str(session.id_session),
                "timestamp": timezone.now().isoformat(),
            }
        ),
    )

    slot1 = Device.objects.get(mac_address="slot1")
    assert slot1.status == DeviceStatus.ONLINE
    assert slot1.last_command_id == "cmd-stop-e2e"
    assert slot1.last_command_action == "STOP"
    assert slot1.last_command_status == "stopped"
    assert DeviceCommandLog.objects.filter(device=slot1, session=session).count() == 3


@pytest.mark.django_db
@override_settings(FRONTEND_BASE_URL="http://fallback.local:5173")
def test_terminal_mobile_session_rejects_unsafe_frontend_origin(api_client):
    """Keep the configured frontend URL when the kiosk sends a malformed origin."""
    response = api_client.post(
        reverse("api-terminal-mobile-session-create"),
        {
            "frontend_origin": "javascript:alert(1)",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    token = response.data["mobile_session"]["token"]
    assert response.data["url"] == f"http://fallback.local:5173/mobile-session.html?token={token}"
