from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import Emplacement, Station


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        pseudo="user",
        email="user@example.com",
        password="UserPass123!",
    )


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_user(
        pseudo="admin",
        email="admin@example.com",
        password="AdminPass123!",
        is_staff=True,
    )


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def station(db):
    return Station.objects.create(
        nom="Station Centre",
        localisation_text="Centre-ville",
        latitude=48.8566,
        longitude=2.3522,
        statut="active",
    )


@pytest.fixture
def emplacements(station):
    return [
        Emplacement.objects.create(
            station=station,
            numero=numero,
            statut="disponible",
            lock_state="verrouille",
        )
        for numero in (1, 2, 3)
    ]


@pytest.fixture
def reservation_start():
    return timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
