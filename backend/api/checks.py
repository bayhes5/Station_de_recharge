"""Custom deployment checks for the charging station backend."""

from __future__ import annotations

import os

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


INSECURE_SECRET_KEYS = {
    "dev-key",
    "change-me",
    "change-me-in-local-dev",
    "test-secret-key-for-pytest-only-keep-it-long-enough-for-jwt",
}

INSECURE_TERMINAL_SECRETS = {
    "",
    "change-me-terminal-secret",
    "dev-terminal-secret",
}

INSECURE_GRAFANA_PASSWORDS = {
    "",
    "admin",
    "password",
    "change-me",
}


def _setting_text(name, default=""):
    """Return a stripped textual representation of a Django setting."""
    return str(getattr(settings, name, default) or "").strip()


@register(Tags.security, deploy=True)
def station_deployment_checks(app_configs, **kwargs):
    """Report project-specific settings that are unsafe for production."""
    messages = []

    secret_key = _setting_text("SECRET_KEY")
    if secret_key in INSECURE_SECRET_KEYS or len(secret_key) < 32:
        messages.append(
            Error(
                "SECRET_KEY must be replaced by a long random value before production.",
                id="api.E001",
            )
        )

    terminal_secret = _setting_text("TERMINAL_API_SECRET")
    if terminal_secret in INSECURE_TERMINAL_SECRETS or len(terminal_secret) < 24:
        messages.append(
            Error(
                "TERMINAL_API_SECRET must be set to a long random value before production.",
                id="api.E002",
            )
        )

    if not getattr(settings, "JWT_REFRESH_COOKIE_SECURE", False):
        messages.append(
            Error(
                "JWT_REFRESH_COOKIE_SECURE must be True in production.",
                id="api.E003",
            )
        )

    if not getattr(settings, "SESSION_COOKIE_SECURE", False):
        messages.append(
            Error(
                "SESSION_COOKIE_SECURE must be True in production.",
                id="api.E004",
            )
        )

    if not getattr(settings, "CSRF_COOKIE_SECURE", False):
        messages.append(
            Error(
                "CSRF_COOKIE_SECURE must be True in production.",
                id="api.E005",
            )
        )

    if getattr(settings, "SECURE_HSTS_SECONDS", 0) <= 0:
        messages.append(
            Warning(
                "SECURE_HSTS_SECONDS should be enabled after HTTPS validation.",
                id="api.W001",
            )
        )

    if "*" in getattr(settings, "ALLOWED_HOSTS", []):
        messages.append(
            Warning(
                "ALLOWED_HOSTS should not contain '*' in production.",
                id="api.W002",
            )
        )

    if not _setting_text("MQTT_USERNAME") or not _setting_text("MQTT_PASSWORD"):
        messages.append(
            Warning(
                "MQTT_USERNAME and MQTT_PASSWORD should be configured for production broker access.",
                id="api.W003",
            )
        )

    if not getattr(settings, "MQTT_TLS_ENABLED", False):
        messages.append(
            Warning(
                "MQTT_TLS_ENABLED should be enabled when MQTT traffic leaves a trusted local network.",
                id="api.W004",
            )
        )

    grafana_password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "").strip()
    if grafana_password in INSECURE_GRAFANA_PASSWORDS:
        messages.append(
            Warning(
                "GRAFANA_ADMIN_PASSWORD should not use an empty or default demo value.",
                id="api.W005",
            )
        )

    return messages
