from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import Reservation

KEYPAD_CODE_ALPHABET = set("0123456789ABCD")


@pytest.mark.django_db
def test_availability_returns_counts(authenticated_client, station, emplacements, reservation_start):
    response = authenticated_client.get(
        reverse("api-reservation-availability"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "date_fin": (reservation_start + timedelta(minutes=30)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["available"] is True
    assert response.data["available_count"] == 3
    assert response.data["total_count"] == 3


@pytest.mark.django_db
def test_availability_requires_existing_station(authenticated_client, reservation_start):
    response = authenticated_client.get(
        reverse("api-reservation-availability"),
        {
            "station": "00000000-0000-0000-0000-000000000000",
            "date_debut": reservation_start.isoformat(),
            "date_fin": (reservation_start + timedelta(minutes=30)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_availability_rejects_non_aligned_slot(authenticated_client, station, reservation_start):
    start = reservation_start + timedelta(minutes=5)
    response = authenticated_client.get(
        reverse("api-reservation-availability"),
        {
            "station": str(station.id_station),
            "date_debut": start.isoformat(),
            "date_fin": (start + timedelta(minutes=30)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_availability_rejects_past_slot(authenticated_client, station):
    start = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    response = authenticated_client.get(
        reverse("api-reservation-availability"),
        {
            "station": str(station.id_station),
            "date_debut": start.isoformat(),
            "date_fin": (start + timedelta(minutes=30)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_reservation_creation_rejects_unknown_station(authenticated_client, reservation_start):
    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": "00000000-0000-0000-0000-000000000000",
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_reservation_creation_rejects_past_slot(authenticated_client, station):
    start = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": start.isoformat(),
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_reservation_creation_rejects_requested_overlapping_emplacement(
    authenticated_client,
    user,
    station,
    emplacements,
    reservation_start,
):
    other_user = get_user_model().objects.create_user(
        pseudo="overlap-owner",
        email="overlap-owner@example.com",
        password="OtherPass123!",
    )
    Reservation.objects.create(
        utilisateur=other_user,
        emplacement=emplacements[0],
        reference_code="OVRLP1",
        auth_choice="qr",
        date_debut=reservation_start,
        date_fin=reservation_start + timedelta(minutes=30),
        statut="confirmee",
    )

    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "emplacement": str(emplacements[0].id_emplacement),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_reservation_creation_rejects_when_station_is_full(
    authenticated_client,
    user,
    station,
    emplacements,
    reservation_start,
):
    for index, emplacement in enumerate(emplacements, start=1):
        other_user = get_user_model().objects.create_user(
            pseudo=f"other{index}",
            email=f"other{index}@example.com",
            password="OtherPass123!",
        )
        Reservation.objects.create(
            utilisateur=other_user,
            emplacement=emplacement,
            reference_code=f"FULL{index}",
            auth_choice="qr",
            date_debut=reservation_start,
            date_fin=reservation_start + timedelta(minutes=30),
            statut="confirmee",
        )

    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_user_reservations_only_returns_owned_rows(authenticated_client, user, station, emplacements, reservation_start):
    other_user = get_user_model().objects.create_user(
        pseudo="other",
        email="other@example.com",
        password="OtherPass123!",
    )
    owned = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="OWNED1",
        auth_choice="qr",
        date_debut=reservation_start,
        date_fin=reservation_start + timedelta(minutes=30),
        statut="confirmee",
    )
    Reservation.objects.create(
        utilisateur=other_user,
        emplacement=emplacements[1],
        reference_code="OTHER1",
        auth_choice="qr",
        date_debut=reservation_start,
        date_fin=reservation_start + timedelta(minutes=30),
        statut="confirmee",
    )

    response = authenticated_client.get(reverse("api-reservations"))

    assert response.status_code == status.HTTP_200_OK
    assert [item["id_reservation"] for item in response.data["results"]] == [str(owned.id_reservation)]


@pytest.mark.django_db
def test_user_cannot_cancel_other_user_reservation(api_client, user, station, emplacements, reservation_start):
    owner = get_user_model().objects.create_user(
        pseudo="owner",
        email="owner@example.com",
        password="OwnerPass123!",
    )
    reservation = Reservation.objects.create(
        utilisateur=owner,
        emplacement=emplacements[0],
        reference_code="OWNR1",
        auth_choice="qr",
        date_debut=reservation_start,
        date_fin=reservation_start + timedelta(minutes=30),
        statut="confirmee",
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse("api-reservation-cancel", kwargs={"reservation_id": reservation.id_reservation}))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    reservation.refresh_from_db()
    assert reservation.statut == "confirmee"


@pytest.mark.django_db
def test_user_can_cancel_own_future_reservation(authenticated_client, user, station, emplacements, reservation_start):
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="CANCEL1",
        auth_choice="qr",
        date_debut=reservation_start,
        date_fin=reservation_start + timedelta(minutes=30),
        statut="confirmee",
    )

    response = authenticated_client.post(
        reverse("api-reservation-cancel", kwargs={"reservation_id": reservation.id_reservation})
    )

    assert response.status_code == status.HTTP_200_OK
    reservation.refresh_from_db()
    assert reservation.statut == "annulee"


@pytest.mark.django_db
def test_access_payload_display_does_not_rotate_code(authenticated_client, station, emplacements, reservation_start):
    create_response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "code",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    reservation_id = create_response.data["reservation"]["id_reservation"]
    reservation_code = create_response.data["reservation_code"]
    created_value = create_response.data["access_payload"]["value"]
    assert len(reservation_code) == 8
    assert set(reservation_code) <= KEYPAD_CODE_ALPHABET
    assert len(created_value) == 12
    assert set(created_value) <= KEYPAD_CODE_ALPHABET

    first_display = authenticated_client.post(
        reverse("api-reservation-access-payload", kwargs={"reservation_id": reservation_id})
    )
    second_display = authenticated_client.post(
        reverse("api-reservation-access-payload", kwargs={"reservation_id": reservation_id})
    )

    assert first_display.status_code == status.HTTP_200_OK
    assert second_display.status_code == status.HTTP_200_OK
    assert first_display.data["access_payload"]["value"] == created_value
    assert second_display.data["access_payload"]["value"] == created_value


@pytest.mark.django_db
def test_access_payload_display_does_not_rotate_qr(authenticated_client, station, emplacements, reservation_start):
    create_response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "qr",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    reservation_code = create_response.data["reservation_code"]
    reservation_id = create_response.data["reservation"]["id_reservation"]
    created_value = create_response.data["access_payload"]["value"]
    assert len(reservation_code) == 8
    assert set(reservation_code) <= KEYPAD_CODE_ALPHABET

    display_response = authenticated_client.post(
        reverse("api-reservation-access-payload", kwargs={"reservation_id": reservation_id})
    )

    assert display_response.status_code == status.HTTP_200_OK
    assert display_response.data["access_payload"]["value"] == created_value
    assert display_response.data["access_payload"]["qr_svg"]
