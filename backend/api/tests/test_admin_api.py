from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import Authentification, Emplacement, JournalSecurite, ProfilUtilisateur, Reservation, Station, TypeAuth


def hash_secret(value):
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.mark.django_db
def test_admin_overview_requires_staff(authenticated_client):
    response = authenticated_client.get(reverse("api-admin-overview"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_overview_returns_counts(admin_client, station, emplacements):
    response = admin_client.get(reverse("api-admin-overview"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stats"]["stations_total"] == 1
    assert response.data["stats"]["emplacements_total"] == 3


@pytest.mark.django_db
def test_admin_can_create_user(admin_client):
    response = admin_client.post(
        reverse("api-admin-users"),
        {
            "pseudo": "created",
            "email": "created@example.com",
            "password": "CreatedPass123!",
            "nom": "Created User",
            "telephone": "0600000000",
            "is_staff": False,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = get_user_model().objects.get(pseudo="created")
    assert user.email == "created@example.com"
    assert user.check_password("CreatedPass123!")
    assert user.profil.nom == "Created User"


@pytest.mark.django_db
def test_admin_user_create_requires_required_fields(admin_client):
    response = admin_client.post(
        reverse("api-admin-users"),
        {"pseudo": "missing-password", "email": "missing@example.com"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_admin_can_patch_user(admin_client, user):
    ProfilUtilisateur.objects.create(utilisateur=user, nom="Old", telephone="")

    response = admin_client.patch(
        reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}),
        {"nom": "Updated User", "is_staff": True},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.is_staff is True
    assert user.profil.nom == "Updated User"


@pytest.mark.django_db
def test_admin_can_delete_user(admin_client):
    user = get_user_model().objects.create_user(
        pseudo="delete-me",
        email="delete-me@example.com",
        password="DeletePass123!",
    )

    response = admin_client.delete(reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not get_user_model().objects.filter(id_user=user.id_user).exists()


@pytest.mark.django_db
def test_admin_can_list_create_and_revoke_user_rfid(admin_client, admin_user, user):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    old_badge = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("OLD-RFID"),
        display_value="OLD-RFID",
        expiration=timezone.now() + timedelta(days=365),
    )

    create_response = admin_client.post(
        reverse("api-admin-user-auth-methods", kwargs={"user_id": user.id_user}),
        {"auth_value": "RFID-SECRET-1234"},
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["auth_method"]["display_value"] == "****1234"
    auth_id = create_response.data["auth_method"]["id_auth"]
    old_badge.refresh_from_db()
    assert old_badge.is_active is False

    list_response = admin_client.get(reverse("api-admin-user-auth-methods", kwargs={"user_id": user.id_user}))

    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.data["results"][0]["display_value"] == "****1234"
    assert "RFID-SECRET-1234" not in str(list_response.data)

    revoke_response = admin_client.post(
        reverse(
            "api-admin-user-auth-method-revoke",
            kwargs={"user_id": user.id_user, "auth_id": auth_id},
        )
    )

    assert revoke_response.status_code == status.HTTP_204_NO_CONTENT
    auth_method = Authentification.objects.get(id_auth=auth_id)
    assert auth_method.is_active is False
    assert JournalSecurite.objects.filter(
        utilisateur=user,
        action__contains=f"admin:{admin_user.pseudo}:rfid_revoked",
    ).exists()


@pytest.mark.django_db
def test_admin_can_regenerate_and_revoke_temporary_access(admin_client, admin_user, user, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("OLD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="ADMINCD1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() + timedelta(minutes=10),
        date_fin=timezone.now() + timedelta(minutes=40),
        statut="confirmee",
    )

    regenerate_response = admin_client.post(
        reverse("api-admin-reservation-access-payload", kwargs={"reservation_id": reservation.id_reservation})
    )

    assert regenerate_response.status_code == status.HTTP_200_OK
    assert regenerate_response.data["access_payload"]["mode"] == "code"
    assert regenerate_response.data["access_payload"]["value"].startswith("CODE-")
    reservation.refresh_from_db()
    reservation.authentification.refresh_from_db()
    assert reservation.authentification.is_active is True

    revoke_response = admin_client.post(
        reverse("api-admin-reservation-access-revoke", kwargs={"reservation_id": reservation.id_reservation})
    )

    assert revoke_response.status_code == status.HTTP_200_OK
    reservation.authentification.refresh_from_db()
    assert reservation.authentification.is_active is False
    assert JournalSecurite.objects.filter(
        utilisateur=user,
        action__contains=f"admin:{admin_user.pseudo}:temporary_access_revoked",
    ).exists()


@pytest.mark.django_db
def test_admin_can_crud_station(admin_client):
    create_response = admin_client.post(
        reverse("api-admin-stations"),
        {
            "nom": "Station Nord",
            "localisation_text": "Quartier Nord",
            "latitude": 48.9,
            "longitude": 2.4,
            "statut": "active",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    station_id = create_response.data["id_station"]

    patch_response = admin_client.patch(
        reverse("api-admin-station-detail", kwargs={"station_id": station_id}),
        {"statut": "maintenance"},
        format="json",
    )

    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["statut"] == "maintenance"

    delete_response = admin_client.delete(reverse("api-admin-station-detail", kwargs={"station_id": station_id}))

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not Station.objects.filter(id_station=station_id).exists()


@pytest.mark.django_db
def test_admin_can_crud_emplacement(admin_client, station):
    create_response = admin_client.post(
        reverse("api-admin-emplacements"),
        {
            "station": str(station.id_station),
            "numero": 1,
            "statut": "disponible",
            "lock_state": "verrouille",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    emplacement_id = create_response.data["id_emplacement"]

    patch_response = admin_client.patch(
        reverse("api-admin-emplacement-detail", kwargs={"emplacement_id": emplacement_id}),
        {"statut": "maintenance"},
        format="json",
    )

    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["statut"] == "maintenance"

    delete_response = admin_client.delete(
        reverse("api-admin-emplacement-detail", kwargs={"emplacement_id": emplacement_id})
    )

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not Emplacement.objects.filter(id_emplacement=emplacement_id).exists()


@pytest.mark.django_db
def test_non_staff_cannot_create_station(authenticated_client):
    response = authenticated_client.post(
        reverse("api-admin-stations"),
        {
            "nom": "Forbidden",
            "localisation_text": "Forbidden",
            "latitude": 48.0,
            "longitude": 2.0,
            "statut": "active",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
