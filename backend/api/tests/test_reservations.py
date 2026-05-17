from datetime import timedelta
import re

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import JournalSecurite, ProfilUtilisateur, Reservation

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
    assert response.data["duration_minutes"] == 30


@pytest.mark.django_db
def test_availability_accepts_longer_supported_duration(authenticated_client, station, emplacements, reservation_start):
    response = authenticated_client.get(
        reverse("api-reservation-availability"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "date_fin": (reservation_start + timedelta(hours=2)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["duration_minutes"] == 120


@pytest.mark.django_db
def test_availability_rejects_unsupported_duration(authenticated_client, station, reservation_start):
    response = authenticated_client.get(
        reverse("api-reservation-availability"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "date_fin": (reservation_start + timedelta(minutes=90)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


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
def test_reservation_creation_uses_default_one_hour_duration(authenticated_client, station, emplacements, reservation_start):
    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    reservation = Reservation.objects.get(id_reservation=response.data["reservation"]["id_reservation"])
    assert reservation.date_fin == reservation.date_debut + timedelta(hours=1)
    assert response.data["reservation"]["duration_minutes"] == 60


@pytest.mark.django_db
def test_reservation_creation_accepts_supported_duration(authenticated_client, station, emplacements, reservation_start):
    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "duration_minutes": 120,
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    reservation = Reservation.objects.get(id_reservation=response.data["reservation"]["id_reservation"])
    assert reservation.date_fin == reservation.date_debut + timedelta(hours=2)


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
def test_reservation_creation_allows_adjacent_paid_window_before_next_reservation(
    authenticated_client,
    user,
    station,
    emplacements,
    reservation_start,
):
    other_user = get_user_model().objects.create_user(
        pseudo="adjacent-next-owner",
        email="adjacent-next-owner@example.com",
        password="OtherPass123!",
    )
    Reservation.objects.create(
        utilisateur=other_user,
        emplacement=emplacements[0],
        reference_code="ADJAC1",
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
            "date_debut": (reservation_start - timedelta(hours=1)).isoformat(),
            "duration_minutes": 60,
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    reservation = Reservation.objects.get(id_reservation=response.data["reservation"]["id_reservation"])
    assert reservation.emplacement == emplacements[0]
    assert reservation.date_fin == reservation_start


@pytest.mark.django_db
def test_reservation_creation_allows_adjacent_paid_window_after_previous_reservation(
    authenticated_client,
    user,
    station,
    emplacements,
    reservation_start,
):
    other_user = get_user_model().objects.create_user(
        pseudo="adjacent-prev-owner",
        email="adjacent-prev-owner@example.com",
        password="OtherPass123!",
    )
    Reservation.objects.create(
        utilisateur=other_user,
        emplacement=emplacements[0],
        reference_code="ADJAC2",
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
            "date_debut": (reservation_start + timedelta(minutes=30)).isoformat(),
            "duration_minutes": 60,
            "auth_mode": "qr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    reservation = Reservation.objects.get(id_reservation=response.data["reservation"]["id_reservation"])
    assert reservation.emplacement == emplacements[0]
    assert reservation.date_debut == reservation_start + timedelta(minutes=30)


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
    user = get_user_model().objects.get(pseudo="user")
    ProfilUtilisateur.objects.create(utilisateur=user, nom="User", telephone="+33600000000")
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
    assert len(reservation_code) == 8
    assert set(reservation_code) <= KEYPAD_CODE_ALPHABET
    assert create_response.data["access_payload"]["mode"] == "code"
    assert create_response.data["access_payload"]["delivery_channel"] == "sms"
    assert "value" not in create_response.data["access_payload"]

    first_display = authenticated_client.post(
        reverse("api-reservation-access-payload", kwargs={"reservation_id": reservation_id})
    )
    second_display = authenticated_client.post(
        reverse("api-reservation-access-payload", kwargs={"reservation_id": reservation_id})
    )

    assert first_display.status_code == status.HTTP_200_OK
    assert second_display.status_code == status.HTTP_200_OK
    assert first_display.data["access_payload"]["delivery_channel"] == "sms"
    assert second_display.data["access_payload"]["delivery_channel"] == "sms"
    assert "value" not in first_display.data["access_payload"]
    assert "value" not in second_display.data["access_payload"]


@pytest.mark.django_db
def test_sms_code_requires_phone_number(authenticated_client, station, emplacements, reservation_start):
    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "code",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "telephone" in response.data


@pytest.mark.django_db
@override_settings(SMS_REQUIRE_VERIFIED_PHONE=True)
def test_sms_code_requires_verified_phone_when_enabled(authenticated_client, user, station, emplacements, reservation_start):
    ProfilUtilisateur.objects.create(
        utilisateur=user,
        nom="User",
        telephone="+33600000000",
        telephone_verifie=False,
    )

    response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "code",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "vérifié" in response.data["telephone"]


@pytest.mark.django_db
def test_sms_code_can_be_sent_and_used(
    authenticated_client,
    api_client,
    user,
    station,
    emplacements,
    reservation_start,
    monkeypatch,
):
    ProfilUtilisateur.objects.create(utilisateur=user, nom="User", telephone="+33600000000")
    sent_messages = []

    def fake_send_sms(phone_number, message):
        from api.services.sms import SmsResult

        sent_messages.append((phone_number, message))
        return SmsResult(backend="test", message_id="sms-1")

    monkeypatch.setattr("api.views.send_sms", fake_send_sms)
    create_response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "code",
        },
        format="json",
    )
    reservation_id = create_response.data["reservation"]["id_reservation"]

    send_response = authenticated_client.post(
        reverse("api-reservation-send-access-code", kwargs={"reservation_id": reservation_id})
    )

    assert send_response.status_code == status.HTTP_200_OK
    assert send_response.data["sms"]["recipient_hint"] == "******0000"
    assert "value" not in send_response.data["access_payload"]
    assert sent_messages[0][0] == "+33600000000"
    sms_code = re.search(r"\b[0-9A-D]{12}\b", sent_messages[0][1]).group(0)
    Reservation.objects.filter(id_reservation=reservation_id).update(
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
    )

    terminal_response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": create_response.data["reservation_code"],
            "auth_mode": "code",
            "auth_value": sms_code,
        },
        format="json",
    )

    assert terminal_response.status_code == status.HTTP_200_OK
    assert JournalSecurite.objects.filter(
        utilisateur=user,
        action__contains="sms_access_code_sent",
    ).exists()


@pytest.mark.django_db
def test_sms_resend_is_rate_limited(authenticated_client, user, station, emplacements, reservation_start, monkeypatch):
    ProfilUtilisateur.objects.create(utilisateur=user, nom="User", telephone="+33600000000")
    sent_messages = []

    def fake_send_sms(phone_number, message):
        from api.services.sms import SmsResult

        sent_messages.append((phone_number, message))
        return SmsResult(backend="test", message_id=f"sms-{len(sent_messages)}")

    monkeypatch.setattr("api.views.send_sms", fake_send_sms)
    create_response = authenticated_client.post(
        reverse("api-reservations"),
        {
            "station": str(station.id_station),
            "date_debut": reservation_start.isoformat(),
            "auth_mode": "code",
        },
        format="json",
    )
    reservation_id = create_response.data["reservation"]["id_reservation"]
    send_url = reverse("api-reservation-send-access-code", kwargs={"reservation_id": reservation_id})

    first_response = authenticated_client.post(send_url)
    second_response = authenticated_client.post(send_url)

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert second_response.data["retry_after_seconds"] > 0
    assert len(sent_messages) == 1


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
