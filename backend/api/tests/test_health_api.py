import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_live_is_public():
    response = APIClient().get(reverse("api-health-live"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["service"] == "station-backend"


@pytest.mark.django_db
@override_settings(TERMINAL_API_SECRET="test-terminal-secret")
def test_health_ready_checks_database_cache_and_config():
    response = APIClient().get(reverse("api-health-ready"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["checks"]["database"]["ok"] is True
    assert response.data["checks"]["cache"]["ok"] is True
    assert response.data["checks"]["config"]["ok"] is True


@pytest.mark.django_db
def test_health_ready_returns_503_when_a_dependency_fails(monkeypatch):
    def failed_database_check():
        return {"ok": False, "detail": "database unavailable"}

    monkeypatch.setattr("api.health_views._check_database_health", failed_database_check)

    response = APIClient().get(reverse("api-health-ready"))

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.data["status"] == "degraded"
    assert response.data["checks"]["database"]["detail"] == "database unavailable"
