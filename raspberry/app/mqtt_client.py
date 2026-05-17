"""MQTT helper used by the Raspberry kiosk."""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


CONFIRMED_ACK_STATUSES = {
    "START": {"accepted", "reserved", "ready", "charging", "charging_started"},
    "STOP": {"accepted", "stopped", "idle"},
    "LOCK": {"accepted", "locked"},
    "UNLOCK": {"accepted", "unlocked"},
}
REJECTED_ACK_STATUSES = {"denied", "error", "failed", "fault", "rejected"}


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
    ack_timeout_seconds: float = float(os.environ.get("MQTT_ACK_TIMEOUT_SECONDS", "2.5"))
    ack_required: bool = os.environ.get("MQTT_ACK_REQUIRED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def slot_topic(slot_id: str, suffix: str = "cmd", settings: MqttSettings | None = None) -> str:
    """Build the MQTT topic for one slot command."""

    mqtt_settings = settings or MqttSettings()
    return f"{mqtt_settings.base_topic}/{slot_id}/{suffix}"


def _decode_ack(raw_payload: bytes) -> dict[str, Any]:
    """Decode an ESP32 ACK payload into a dictionary."""
    text = raw_payload.decode("utf-8", errors="replace")
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    return decoded if isinstance(decoded, dict) else {"raw": decoded}


def _ack_matches(ack_payload: dict[str, Any], command_id: str, action: str) -> bool:
    """Return whether an ACK corresponds to the command just published."""
    ack_command_id = str(ack_payload.get("command_id") or "").strip()
    ack_action = str(ack_payload.get("action") or "").strip().upper()
    if ack_command_id:
        return ack_command_id == command_id and (not ack_action or ack_action == action.upper())
    return bool(ack_action and ack_action == action.upper())


def _ack_status(ack_payload: dict[str, Any] | None) -> str:
    """Return the normalized status carried by an ESP32 ACK."""
    if not ack_payload:
        return ""
    return str(ack_payload.get("status") or ack_payload.get("state") or "").strip().lower()


def _ack_message(ack_payload: dict[str, Any] | None) -> str:
    """Return a readable diagnostic message from an ESP32 ACK."""
    if not ack_payload:
        return ""
    return str(ack_payload.get("message") or "").strip()


def _ack_confirms_command(ack_payload: dict[str, Any] | None, action: str) -> bool:
    """Return whether an ACK is an operational confirmation."""
    status = _ack_status(ack_payload)
    if not status or status in REJECTED_ACK_STATUSES:
        return False
    return status in CONFIRMED_ACK_STATUSES.get(action.upper(), {"accepted"})


def publish_slot_command(slot_id: str, action: str, **metadata: Any) -> dict[str, Any]:
    """Publish a command to one ESP32 slot through the local MQTT broker."""

    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("paho-mqtt n'est pas installe cote Raspberry.") from exc

    settings = MqttSettings()
    command_id = str(metadata.pop("command_id", "") or uuid.uuid4())
    action = action.upper()
    payload = {
        "command_id": command_id,
        "action": action,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    command_topic = slot_topic(slot_id, settings=settings)
    ack_topic = slot_topic(slot_id, suffix="ack", settings=settings)
    ack_event = threading.Event()
    subscribed_event = threading.Event()
    ack_payload: dict[str, Any] | None = None

    def on_message(_client, _userdata, message):
        nonlocal ack_payload
        decoded_ack = _decode_ack(message.payload)
        if _ack_matches(decoded_ack, command_id=command_id, action=action):
            ack_payload = {
                "topic": message.topic,
                "payload": decoded_ack,
            }
            ack_event.set()

    def on_subscribe(*_args):
        subscribed_event.set()

    client = mqtt.Client(client_id=settings.client_id)
    client.on_message = on_message
    client.on_subscribe = on_subscribe

    if settings.username:
        client.username_pw_set(settings.username, settings.password)
    if settings.tls_enabled:
        client.tls_set()

    client.connect(settings.host, settings.port, settings.keepalive)
    client.loop_start()
    client.subscribe(ack_topic, qos=settings.qos)
    subscribed_event.wait(timeout=1)
    result = client.publish(
        command_topic,
        json.dumps(payload),
        qos=settings.qos,
    )
    result.wait_for_publish(timeout=2)
    ack_event.wait(timeout=settings.ack_timeout_seconds)
    client.loop_stop()
    client.disconnect()

    ack_status = _ack_status(ack_payload["payload"] if ack_payload else None)
    ack_message = _ack_message(ack_payload["payload"] if ack_payload else None)
    command_confirmed = _ack_confirms_command(
        ack_payload["payload"] if ack_payload else None,
        action=action,
    )

    if ack_status in REJECTED_ACK_STATUSES:
        detail = f": {ack_message}" if ack_message else ""
        raise RuntimeError(f"Commande MQTT {action} refusee par ESP32 sur {ack_topic}{detail}.")

    if settings.ack_required and ack_payload is None:
        raise RuntimeError(f"Commande MQTT publiee sans confirmation ESP32 sur {ack_topic}.")
    if settings.ack_required and not command_confirmed:
        detail = f" status={ack_status}" if ack_status else ""
        raise RuntimeError(f"ACK ESP32 non confirmant pour {action} sur {ack_topic}{detail}.")

    return {
        "topic": command_topic,
        "ack_topic": ack_topic,
        "ack_required": settings.ack_required,
        "ack_received": ack_payload is not None,
        "ack_status": ack_status,
        "command_confirmed": command_confirmed,
        "ack_timeout_seconds": settings.ack_timeout_seconds,
        "command": payload,
        "ack": ack_payload,
    }
