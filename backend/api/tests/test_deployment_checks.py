from django.test import override_settings

from api.checks import station_deployment_checks


def _check_ids():
    return {message.id for message in station_deployment_checks(None)}


@override_settings(
    ALLOWED_HOSTS=["*"],
    CSRF_COOKIE_SECURE=False,
    JWT_REFRESH_COOKIE_SECURE=False,
    MQTT_ACK_REQUIRED=False,
    MQTT_PASSWORD="",
    MQTT_TLS_ENABLED=False,
    MQTT_USERNAME="",
    SECRET_KEY="dev-key",
    SECURE_HSTS_SECONDS=0,
    SESSION_COOKIE_SECURE=False,
    TERMINAL_API_SECRET="change-me-terminal-secret",
)
def test_station_deployment_checks_report_unsafe_settings(monkeypatch):
    """Report every project-specific production safety issue."""
    monkeypatch.setenv("GRAFANA_ADMIN_PASSWORD", "admin")

    ids = _check_ids()

    assert {
        "api.E001",
        "api.E002",
        "api.E003",
        "api.E004",
        "api.E005",
        "api.E006",
        "api.W001",
        "api.W002",
        "api.W003",
        "api.W004",
        "api.W005",
    }.issubset(ids)


@override_settings(
    ALLOWED_HOSTS=["station.example.com"],
    CSRF_COOKIE_SECURE=True,
    JWT_REFRESH_COOKIE_SECURE=True,
    MQTT_ACK_REQUIRED=True,
    MQTT_PASSWORD="mqtt-production-password",
    MQTT_TLS_ENABLED=True,
    MQTT_USERNAME="station-backend",
    SECRET_KEY="station-production-secret-key-with-enough-random-length",
    SECURE_HSTS_SECONDS=31536000,
    SESSION_COOKIE_SECURE=True,
    TERMINAL_API_SECRET="terminal-production-secret-with-enough-length",
)
def test_station_deployment_checks_accept_hardened_settings(monkeypatch):
    """Accept a hardened production-like configuration."""
    monkeypatch.setenv("GRAFANA_ADMIN_PASSWORD", "grafana-production-password")

    assert station_deployment_checks(None) == []
