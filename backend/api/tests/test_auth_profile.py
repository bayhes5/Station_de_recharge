import pytest
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from api.models import ProfilUtilisateur


@pytest.mark.django_db
def test_login_accepts_pseudo(api_client, user):
    response = api_client.post(
        reverse("api-login"),
        {"identifiant": "user", "password": "UserPass123!"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["user"]["pseudo"] == user.pseudo
    assert response.data["access"]
    assert "refresh" not in response.data
    assert settings.JWT_REFRESH_COOKIE_NAME in response.cookies


@pytest.mark.django_db
def test_login_accepts_email_case_insensitive(api_client, user):
    response = api_client.post(
        reverse("api-login"),
        {"identifiant": "USER@EXAMPLE.COM", "password": "UserPass123!"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["user"]["email"] == user.email


@pytest.mark.django_db
def test_login_rejects_invalid_password(api_client, user):
    response = api_client.post(
        reverse("api-login"),
        {"identifiant": user.pseudo, "password": "WrongPass123!"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_requires_authentication(api_client):
    response = api_client.get(reverse("api-me"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_returns_current_profile(authenticated_client, user):
    ProfilUtilisateur.objects.create(utilisateur=user, nom="User Name", telephone="0600000000")

    response = authenticated_client.get(reverse("api-me"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["user"]["pseudo"] == user.pseudo
    assert response.data["profile"]["nom"] == "User Name"


@pytest.mark.django_db
def test_profile_patch_updates_user_and_profile(authenticated_client, user):
    response = authenticated_client.patch(
        reverse("api-profile"),
        {
            "pseudo": "newuser",
            "email": "newuser@example.com",
            "telephone": "0611223344",
            "nom": "New User",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.pseudo == "newuser"
    assert user.email == "newuser@example.com"
    assert user.profil.nom == "New User"
    assert user.profil.telephone == "0611223344"


@pytest.mark.django_db
def test_change_password_requires_current_password(authenticated_client, user):
    response = authenticated_client.post(
        reverse("api-change-password"),
        {
            "current_password": "BadPass123!",
            "new_password": "NewUserPass123!",
            "confirm_password": "NewUserPass123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    user.refresh_from_db()
    assert user.check_password("UserPass123!")


@pytest.mark.django_db
def test_change_password_updates_password(authenticated_client, user):
    response = authenticated_client.post(
        reverse("api-change-password"),
        {
            "current_password": "UserPass123!",
            "new_password": "NewUserPass123!",
            "confirm_password": "NewUserPass123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("NewUserPass123!")


@pytest.mark.django_db
def test_delete_profile_deletes_account(authenticated_client, user):
    response = authenticated_client.delete(reverse("api-profile"))

    assert response.status_code == status.HTTP_200_OK
    assert not get_user_model().objects.filter(id_user=user.id_user).exists()
