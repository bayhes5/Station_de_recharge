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

SMS_PROVIDER_REQUIRED_SETTINGS = {
    "twilio": ("SMS_TWILIO_ACCOUNT_SID", "SMS_TWILIO_AUTH_TOKEN", "SMS_TWILIO_FROM"),
    "brevo": ("SMS_BREVO_API_KEY",),
    "ovh": (
        "SMS_OVH_APPLICATION_KEY",
        "SMS_OVH_APPLICATION_SECRET",
        "SMS_OVH_CONSUMER_KEY",
        "SMS_OVH_SERVICE_NAME",
    ),
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

    if not getattr(settings, "MQTT_ACK_REQUIRED", False):
        messages.append(
            Error(
                "MQTT_ACK_REQUIRED must be True in production so START/STOP commands require ESP32 confirmation.",
                id="api.E006",
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

    sms_backend = _setting_text("SMS_BACKEND", "console").lower()
    if sms_backend in {"console", "disabled"}:
        messages.append(
            Warning(
                "SMS_BACKEND should use a production provider such as twilio, brevo or ovh.",
                id="api.W006",
            )
        )
    for setting_name in SMS_PROVIDER_REQUIRED_SETTINGS.get(sms_backend, ()):
        if not _setting_text(setting_name):
            messages.append(
                Error(
                    f"{setting_name} must be configured when SMS_BACKEND={sms_backend}.",
                    id="api.E007",
                )
            )

    if not getattr(settings, "SMS_REQUIRE_VERIFIED_PHONE", False):
        messages.append(
            Warning(
                "SMS_REQUIRE_VERIFIED_PHONE should be True before production SMS delivery.",
                id="api.W007",
            )
        )

    if not _setting_text("EXPECTED_ESP32_FIRMWARE_VERSION"):
        messages.append(
            Warning(
                "EXPECTED_ESP32_FIRMWARE_VERSION should define the default approved ESP32 firmware.",
                id="api.W008",
            )
        )

    return messages
