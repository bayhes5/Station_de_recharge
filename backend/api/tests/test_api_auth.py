from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.models import Emplacement, Reservation, Station


@pytest.mark.django_db
def test_register_endpoint_returns_tokens_and_user_payload():
    response = APIClient().post(
        reverse("api-register"),
        {
            "pseudo": "bob",
            "email": "bob@example.com",
            "telephone": "0600000000",
            "password": "ValidPass123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["user"]["pseudo"] == "bob"
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_admin_can_reset_user_password():
    user_model = get_user_model()
    admin = user_model.objects.create_user(
        pseudo="admin",
        email="admin@example.com",
        password="AdminPass123!",
        is_staff=True,
    )
    user = user_model.objects.create_user(
        pseudo="jane",
        email="jane@example.com",
        password="OldPass123!",
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.post(reverse("api-admin-user-reset-password", kwargs={"user_id": user.id_user}))

    assert response.status_code == status.HTTP_200_OK
    temporary_password = response.data["temporary_password"]
    assert len(temporary_password) >= 12
    assert any(character.islower() for character in temporary_password)
    assert any(character.isupper() for character in temporary_password)
    assert any(character.isdigit() for character in temporary_password)
    assert any(not character.isalnum() for character in temporary_password)
    user.refresh_from_db()
    assert user.check_password(temporary_password)


@pytest.mark.django_db
def test_regular_user_cannot_reset_user_password():
    user_model = get_user_model()
    requester = user_model.objects.create_user(
        pseudo="requester",
        email="requester@example.com",
        password="RequesterPass123!",
    )
    target = user_model.objects.create_user(
        pseudo="target",
        email="target@example.com",
        password="OldPass123!",
    )
    client = APIClient()
    client.force_authenticate(user=requester)

    response = client.post(reverse("api-admin-user-reset-password", kwargs={"user_id": target.id_user}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    target.refresh_from_db()
    assert target.check_password("OldPass123!")


@pytest.mark.django_db
def test_reservation_creation_assigns_available_emplacement_from_station():
    user = get_user_model().objects.create_user(
        pseudo="driver",
        email="driver@example.com",
        password="DriverPass123!",
    )
    station = Station.objects.create(
        nom="Station Centre",
        localisation_text="Centre-ville",
        latitude=48.8566,
        longitude=2.3522,
        statut="active",
    )
    first_emplacement = Emplacement.objects.create(
        station=station,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )
    Emplacement.objects.create(
        station=station,
        numero=2,
        statut="disponible",
        lock_state="verrouille",
    )
    start = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": start.isoformat(),
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    reservation = Reservation.objects.get(id_reservation=response.data["reservation"]["id_reservation"])
    assert reservation.emplacement == first_emplacement
