from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from api.models import ProfilUtilisateur
from api.serializers import RegisterSerializer, ReservationCreateSerializer


@pytest.mark.django_db
def test_register_serializer_creates_user_and_profile():
    serializer = RegisterSerializer(
        data={
            "pseudo": "alice",
            "email": "alice@example.com",
            "telephone": "0601020304",
            "password": "ValidPass123!",
        }
    )

    assert serializer.is_valid(), serializer.errors
    user = serializer.save()

    assert user.pseudo == "alice"
    assert user.email == "alice@example.com"
    assert user.check_password("ValidPass123!")

    profile = ProfilUtilisateur.objects.get(utilisateur=user)
    assert profile.nom == "alice"
    assert profile.telephone == "0601020304"


@pytest.mark.django_db
def test_register_serializer_rejects_duplicate_pseudo_case_insensitive():
    get_user_model().objects.create_user(
        pseudo="Alice",
        email="first@example.com",
        password="ValidPass123!",
    )

    serializer = RegisterSerializer(
        data={
            "pseudo": "alice",
            "email": "second@example.com",
            "password": "AnotherPass123!",
        }
    )

    assert not serializer.is_valid()
    assert "pseudo" in serializer.errors


def test_reservation_create_serializer_forces_thirty_minute_duration():
    start = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    serializer = ReservationCreateSerializer(
        data={
            "emplacement": "f63c316b-476f-4d5a-b811-cf4e05ca2b51",
            "date_debut": start.isoformat(),
            "auth_mode": "qr",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["date_fin"] == serializer.validated_data["date_debut"] + timedelta(minutes=30)
