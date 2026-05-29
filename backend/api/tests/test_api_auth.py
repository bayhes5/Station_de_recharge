from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.models import Consentement, Emplacement, Reservation, Station


@pytest.mark.django_db
def test_register_endpoint_returns_tokens_and_user_payload():
    response = APIClient().post(
        reverse("api-register"),
        {
            "pseudo": "bob",
            "email": "bob@example.com",
            "telephone": "0600000000",
            "password": "ValidPass123!",
            "cgu_accepted": True,
            "privacy_policy_accepted": True,
            "notifications_accepted": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["user"]["pseudo"] == "bob"
    assert "access" in response.data
    assert "refresh" not in response.data
    assert settings.JWT_REFRESH_COOKIE_NAME in response.cookies

    consentements = {
        consentement.type: consentement.statut
        for consentement in Consentement.objects.filter(utilisateur__pseudo="bob")
    }
    assert consentements == {
        "cgu": "accepte",
        "politique_confidentialite": "accepte",
        "notifications": "accepte",
    }


@pytest.mark.django_db
def test_user_can_read_and_update_optional_consents(authenticated_client, user):
    Consentement.objects.create(utilisateur=user, type="cgu", statut="accepte")
    Consentement.objects.create(
        utilisateur=user,
        type="politique_confidentialite",
        statut="accepte",
    )
    Consentement.objects.create(utilisateur=user, type="notifications", statut="accepte")

    get_response = authenticated_client.get(reverse("api-consentements"))

    assert get_response.status_code == status.HTTP_200_OK
    assert {
        item["type"]: item["statut"]
        for item in get_response.data["current"]
    } == {
        "cgu": "accepte",
        "politique_confidentialite": "accepte",
        "notifications": "accepte",
    }

    patch_response = authenticated_client.patch(
        reverse("api-consentements"),
        {"notifications_accepted": False},
        format="json",
    )

    assert patch_response.status_code == status.HTTP_200_OK
    assert Consentement.objects.filter(
        utilisateur=user,
        type="notifications",
        statut="refuse",
    ).exists()
    assert Consentement.objects.filter(utilisateur=user, type="notifications").count() == 2


@pytest.mark.django_db
def test_user_consent_update_does_not_duplicate_unchanged_status(authenticated_client, user):
    Consentement.objects.create(utilisateur=user, type="notifications", statut="refuse")

    response = authenticated_client.patch(
        reverse("api-consentements"),
        {"notifications_accepted": False},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert Consentement.objects.filter(utilisateur=user, type="notifications").count() == 1


@pytest.mark.django_db
def test_refresh_endpoint_uses_httponly_cookie():
    client = APIClient()
    login_response = client.post(
        reverse("api-login"),
        {
            "identifiant": "cookie-user",
            "password": "CookiePass123!",
        },
        format="json",
    )
    assert login_response.status_code == status.HTTP_401_UNAUTHORIZED

    get_user_model().objects.create_user(
        pseudo="cookie-user",
        email="cookie-user@example.com",
        password="CookiePass123!",
    )
    login_response = client.post(
        reverse("api-login"),
        {
            "identifiant": "cookie-user",
            "password": "CookiePass123!",
        },
        format="json",
    )

    assert login_response.status_code == status.HTTP_200_OK
    assert "refresh" not in login_response.data
    assert login_response.cookies[settings.JWT_REFRESH_COOKIE_NAME]["httponly"]

    refresh_response = client.post(reverse("token_refresh"), {}, format="json")

    assert refresh_response.status_code == status.HTTP_200_OK
    assert "access" in refresh_response.data


@pytest.mark.django_db
def test_logout_clears_refresh_cookie():
    client = APIClient()
    response = client.post(reverse("api-logout"))

    assert response.status_code == status.HTTP_200_OK
    assert settings.JWT_REFRESH_COOKIE_NAME in response.cookies
    assert response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value == ""


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
    assert response.data["email_sent"] is True
    assert "temporary_password" not in response.data
    assert len(mail.outbox) == 1
    temporary_password = next(
        line.removeprefix("Mot de passe provisoire: ")
        for line in mail.outbox[0].body.splitlines()
        if line.startswith("Mot de passe provisoire: ")
    )
    assert len(temporary_password) >= 12
    assert any(character.islower() for character in temporary_password)
    assert any(character.isupper() for character in temporary_password)
    assert any(character.isdigit() for character in temporary_password)
    assert any(not character.isalnum() for character in temporary_password)
    user.refresh_from_db()
    assert user.check_password(temporary_password)
    assert user.must_change_password is True

    login_response = client.post(
        reverse("api-login"),
        {"identifiant": "jane", "password": temporary_password},
        format="json",
    )
    assert login_response.status_code == status.HTTP_200_OK
    assert login_response.data["user"]["must_change_password"] is True


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
