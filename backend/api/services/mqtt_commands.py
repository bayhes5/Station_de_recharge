from __future__ import annotations

import json

from django.conf import settings


def build_slot_command_topic(slot_id: str) -> str:
    """Return the command topic used by one ESP32 slot."""
    return f"{settings.MQTT_BASE_TOPIC}/{slot_id}/cmd"


def publish_slot_command(slot_id: str, action: str, **metadata):
    """Publish a diagnostic command to one ESP32 slot.

    Production kiosk flows should publish from the Raspberry, because it owns the
    local Mosquitto connection and can keep operating during backend outages.
    """
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("Installe paho-mqtt pour publier des commandes MQTT.") from exc

    payload = {"action": action.upper(), **metadata}
    client = mqtt.Client(client_id=f"{settings.MQTT_BACKEND_CLIENT_ID}-cmd")

    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    if settings.MQTT_TLS_ENABLED:
        client.tls_set()

    client.connect(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
    client.publish(
        build_slot_command_topic(slot_id),
        json.dumps(payload),
        qos=settings.MQTT_QOS,
    )
    client.disconnect()
    return payload
