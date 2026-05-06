"""MQTT helper used by the Raspberry kiosk."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MqttSettings:
    """Runtime MQTT settings for the local Raspberry edge client."""

    host: str = os.environ.get("MQTT_HOST", "localhost")
    port: int = int(os.environ.get("MQTT_PORT", "1883"))
    keepalive: int = int(os.environ.get("MQTT_KEEPALIVE", "60"))
    base_topic: str = os.environ.get("MQTT_BASE_TOPIC", "station")
    client_id: str = os.environ.get("MQTT_RASPBERRY_CLIENT_ID", "raspberry-kiosk")
    username: str = os.environ.get("MQTT_USERNAME", "")
    password: str = os.environ.get("MQTT_PASSWORD", "")
    tls_enabled: bool = os.environ.get("MQTT_TLS_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    qos: int = int(os.environ.get("MQTT_QOS", "1"))


def slot_topic(slot_id: str, suffix: str = "cmd", settings: MqttSettings | None = None) -> str:
    """Build the MQTT topic for one slot command."""

    mqtt_settings = settings or MqttSettings()
    return f"{mqtt_settings.base_topic}/{slot_id}/{suffix}"


def publish_slot_command(slot_id: str, action: str, **metadata: Any) -> dict[str, Any]:
    """Publish a command to one ESP32 slot through the local MQTT broker."""

    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("paho-mqtt n'est pas installe cote Raspberry.") from exc

    settings = MqttSettings()
    payload = {"action": action.upper(), **metadata}
    client = mqtt.Client(client_id=settings.client_id)

    if settings.username:
        client.username_pw_set(settings.username, settings.password)
    if settings.tls_enabled:
        client.tls_set()

    client.connect(settings.host, settings.port, settings.keepalive)
    result = client.publish(
        slot_topic(slot_id, settings=settings),
        json.dumps(payload),
        qos=settings.qos,
    )
    result.wait_for_publish(timeout=2)
    client.disconnect()
    return payload
