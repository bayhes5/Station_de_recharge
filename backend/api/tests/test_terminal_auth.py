import hashlib
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import Authentification, Reservation, Session, TypeAuth


def hash_secret(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.mark.django_db
def test_create_auth_method_accepts_rfid(authenticated_client, user):
    response = authenticated_client.post(
        reverse("api-auth-method-create"),
        {"auth_mode": "rfid", "auth_value": "RFID-1234"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["auth_method"]["type_label"] == "RFID"
    assert Authentification.objects.filter(utilisateur=user, type_auth__libelle="RFID").exists()


@pytest.mark.django_db
def test_create_auth_method_rejects_non_rfid(authenticated_client):
    response = authenticated_client.post(
        reverse("api-auth-method-create"),
        {"auth_mode": "qr", "auth_value": "QR-1234"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_delete_auth_method_only_deletes_owned_badge(api_client, user):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    badge = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("RFID-1234"),
        display_value="RFID-1234",
        expiration=timezone.now() + timedelta(days=365),
    )
    other_user = type(user).objects.create_user(
        pseudo="other-badge",
        email="other-badge@example.com",
        password="OtherPass123!",
    )
    api_client.force_authenticate(user=other_user)

    forbidden_response = api_client.delete(reverse("api-auth-method-delete", kwargs={"auth_id": badge.id_auth}))

    assert forbidden_response.status_code == status.HTTP_404_NOT_FOUND
    assert Authentification.objects.filter(id_auth=badge.id_auth).exists()

    api_client.force_authenticate(user=user)
    delete_response = api_client.delete(reverse("api-auth-method-delete", kwargs={"auth_id": badge.id_auth}))

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not Authentification.objects.filter(id_auth=badge.id_auth).exists()


@pytest.mark.django_db
def test_terminal_authenticate_requires_payload(api_client):
    response = api_client.post(reverse("api-terminal-authenticate"), {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_terminal_authenticate_rejects_wrong_secret(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("GOOD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="BADCODE1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": reservation.reference_code,
            "auth_mode": "code",
            "auth_value": "WRONG-CODE",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Session.objects.filter(reservation=reservation).exists()


@pytest.mark.django_db
def test_terminal_authenticate_opens_session_with_valid_code(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("GOOD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="GOODCODE",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": reservation.reference_code,
            "auth_mode": "code",
            "auth_value": "GOOD-CODE",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["session_created"] is True
    reservation.refresh_from_db()
    assert reservation.statut == "active"
    assert Session.objects.filter(reservation=reservation, emplacement=emplacements[0]).exists()
