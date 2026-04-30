import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from api.models import Emplacement, ProfilUtilisateur, Station


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
