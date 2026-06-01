from __future__ import annotations

from django.conf import settings


def configure_mqtt_tls(client) -> None:
    """Apply MQTT TLS settings to a paho client when TLS is enabled."""

    if not settings.MQTT_TLS_ENABLED:
        return
    client.tls_set(ca_certs=settings.MQTT_TLS_CA_CERT or None)
