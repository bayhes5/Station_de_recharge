from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import (
    Alerte,
    Capteur,
    CapteurData,
    Device,
    DeviceCommandLog,
    Emplacement,
    Maintenance,
    ProfilUtilisateur,
    Reservation,
    Session,
    Technicien,
)


@pytest.mark.django_db
def test_stations_catalog_uses_prefetch_and_cache(
    authenticated_client,
    django_assert_num_queries,
    station,
    emplacements,
):
    cache.clear()

    with django_assert_num_queries(4):
        response = authenticated_client.get(reverse("api-stations-catalog"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"][0]["emplacements"]

    with django_assert_num_queries(0):
        cached_response = authenticated_client.get(reverse("api-stations-catalog"))

    assert cached_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_reservation_availability_keeps_constant_query_count(
    authenticated_client,
    django_assert_num_queries,
    station,
    emplacements,
    reservation_start,
):
    for index, emplacement in enumerate(emplacements, start=1):
        other_user = get_user_model().objects.create_user(
            pseudo=f"busy{index}",
            email=f"busy{index}@example.com",
            password="BusyPass123!",
        )
        Reservation.objects.create(
            utilisateur=other_user,
            emplacement=emplacement,
            reference_code=f"BUSY{index}",
            auth_choice="qr",
            date_debut=reservation_start + timedelta(hours=1),
            date_fin=reservation_start + timedelta(hours=1, minutes=30),
            statut="confirmee",
        )

    with django_assert_num_queries(3):
        response = authenticated_client.get(
            reverse("api-reservation-availability"),
            {
                "station": str(station.id_station),
                "date_debut": reservation_start.isoformat(),
                "date_fin": (reservation_start + timedelta(minutes=30)).isoformat(),
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["available_count"] == 3


@pytest.mark.django_db
def test_admin_users_pagination_keeps_constant_query_count(
    admin_client,
    django_assert_num_queries,
):
    User = get_user_model()
    for index in range(12):
        user = User.objects.create_user(
            pseudo=f"member{index}",
            email=f"member{index}@example.com",
            password="MemberPass123!",
        )
        ProfilUtilisateur.objects.create(
            utilisateur=user,
            nom=f"Member {index}",
            telephone="",
        )

    with django_assert_num_queries(2):
        response = admin_client.get(
            reverse("api-admin-users"),
            {"page": 1, "page_size": 5},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] >= 12
    assert len(response.data["results"]) == 5


@pytest.mark.django_db
def test_admin_maintenances_pagination_keeps_constant_query_count(
    admin_client,
    django_assert_num_queries,
    station,
    admin_user,
    reservation_start,
):
    technicien = Technicien.objects.create(
        utilisateur=admin_user,
        nom="Tech Perf",
        email="tech-perf@example.com",
        telephone="",
    )
    for index in range(8):
        Maintenance.objects.create(
            station=station,
            technicien=technicien,
            type=f"Controle {index}",
            description="Controle periodique",
            status="planifiee",
            date_planifiee=reservation_start + timedelta(days=index),
        )

    with django_assert_num_queries(2):
        response = admin_client.get(
            reverse("api-admin-maintenances"),
            {"page": 1, "page_size": 4},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 8
    assert len(response.data["results"]) == 4


@pytest.mark.django_db
def test_admin_supervision_keeps_constant_query_count(
    admin_client,
    django_assert_num_queries,
    station,
    borne,
    emplacements,
    user,
):
    """Keep the supervision snapshot bounded as devices and command logs grow."""
    now = timezone.now()
    all_emplacements = list(emplacements)
    for numero in range(4, 11):
        all_emplacements.append(
            Emplacement.objects.create(
                station=station,
                borne=borne,
                numero=numero,
                statut="disponible",
                lock_state="verrouille",
            )
        )

    for index, emplacement in enumerate(all_emplacements, start=1):
        device = Device.objects.create(
            emplacement=emplacement,
            type_device="ESP32",
            firmware_version="1.0.0",
            mac_address=f"slot{index}",
            last_seen=now,
            status="charging" if index % 2 else "online",
        )
        capteur = Capteur.objects.create(device=device, type="temperature", unite="C")
        data = CapteurData.objects.create(capteur=capteur, valeur=30 + index, timestamp=now)
        reservation = Reservation.objects.create(
            utilisateur=user,
            emplacement=emplacement,
            reference_code=f"PERF{index:04d}",
            auth_choice="qr",
            date_debut=now - timedelta(minutes=10),
            date_fin=now + timedelta(minutes=20),
            statut="active",
        )
        session = Session.objects.create(
            reservation=reservation,
            emplacement=emplacement,
            start_time=now - timedelta(minutes=5),
        )
        Alerte.objects.create(
            data=data,
            session=session,
            type="overheat",
            message="Température élevée",
            niveau_severite="critical" if index % 3 == 0 else "haute",
            status="active",
            timestamp=now,
        )
        DeviceCommandLog.objects.create(
            device=device,
            session=session,
            command_id=f"cmd-{index}",
            action="START",
            status="accepted",
            message="Emplacement réservé.",
            source="raspberry",
            payload={"command_id": f"cmd-{index}", "action": "START", "status": "accepted"},
            timestamp=now,
        )

    with django_assert_num_queries(6):
        response = admin_client.get(reverse("api-admin-supervision"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stats"]["devices_total"] == 10
    assert response.data["stats"]["active_alerts"] == 10
    assert response.data["stats"]["critical_alerts"] == 3
    assert len(response.data["devices"]) == 10
    assert len(response.data["alerts"]) == 10
    assert len(response.data["measurements"]) == 10
    assert len(response.data["commands"]) == 10
