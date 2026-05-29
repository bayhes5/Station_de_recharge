"""MQTT helper used by the Raspberry kiosk."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mqtt_contract import REJECTED_ACK_STATUSES
from mqtt_contract import ack_confirms_command
from mqtt_contract import ack_status
from mqtt_contract import validate_command_payload


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


def _effective_base_topic(settings: MqttSettings, topic_prefix: str | None = None) -> str:
    """Return the MQTT prefix for the command, preserving local defaults."""

    base_topic = settings.base_topic.strip("/")
    prefix = str(topic_prefix or "").strip("/")
    if not prefix:
        return base_topic
    if prefix == base_topic or prefix.startswith(f"{base_topic}/"):
        return prefix
    if base_topic.endswith(f"/{prefix}"):
        return base_topic
    return f"{base_topic}/{prefix}"


def slot_topic(
    slot_id: str,
    suffix: str = "cmd",
    settings: MqttSettings | None = None,
    topic_prefix: str | None = None,
) -> str:
    """Build the MQTT topic for one slot command."""

    mqtt_settings = settings or MqttSettings()
    return f"{_effective_base_topic(mqtt_settings, topic_prefix=topic_prefix)}/{slot_id}/{suffix}"


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
    return ack_status(ack_payload)


def _ack_message(ack_payload: dict[str, Any] | None) -> str:
    """Return a readable diagnostic message from an ESP32 ACK."""
    if not ack_payload:
        return ""
    return str(ack_payload.get("message") or "").strip()


def _ack_confirms_command(ack_payload: dict[str, Any] | None, action: str) -> bool:
    """Return whether an ACK is an operational confirmation."""
    return ack_confirms_command(ack_payload, action)


class MqttSlotMonitor:
    """Background MQTT subscriber keeping the latest ESP32 slot messages."""

    def __init__(self, settings: MqttSettings | None = None):
        self.settings = settings or MqttSettings()
        self._lock = threading.Lock()
        self._messages: dict[str, dict[str, dict[str, Any]]] = {}
        self._thread: threading.Thread | None = None
        self._running = False
        self.status = "stopped"
        self.detail = ""

    def start(self) -> None:
        """Start the monitor in background if it is not already running."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()

    def snapshot(self, slot_id: str) -> dict[str, Any]:
        """Return the latest known MQTT messages for one slot."""
        normalized_slot = str(slot_id or "").strip()
        with self._lock:
            messages = dict(self._messages.get(normalized_slot, {}))
        telemetry = messages.get("telemetry", {})
        status = messages.get("status", {})
        ack = messages.get("ack", {})
        latest_payload = (
            telemetry.get("payload")
            or status.get("payload")
            or ack.get("payload")
            or {}
        )
        return {
            "slot_id": normalized_slot,
            "monitor": {
                "status": self.status,
                "detail": self.detail,
            },
            "telemetry": telemetry,
            "status": status,
            "ack": ack,
            "latest": latest_payload,
            "cable_present": _extract_bool(
                telemetry.get("payload", {}).get("cable")
                if telemetry.get("payload")
                else status.get("payload", {}).get("cable")
            ),
            "door_closed": _extract_bool(
                telemetry.get("payload", {}).get("door")
                if telemetry.get("payload")
                else status.get("payload", {}).get("door")
            ),
            "state": str(
                latest_payload.get("state")
                or latest_payload.get("status")
                or latest_payload.get("event")
                or ""
            ).strip().lower(),
        }

    def record_message(self, topic: str, raw_payload: bytes | str) -> None:
        """Record one MQTT message. Public to make the parser testable."""
        parsed = _parse_slot_topic(topic)
        if not parsed:
            return
        slot_id, suffix = parsed
        if suffix not in {"telemetry", "status", "ack", "alert"}:
            return
        payload = _decode_ack(
            raw_payload.encode("utf-8") if isinstance(raw_payload, str) else raw_payload
        )
        message = {
            "topic": topic,
            "payload": payload,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._messages.setdefault(slot_id, {})[suffix] = message

    def _run_forever(self) -> None:
        while self._running:
            try:
                self._run_once()
            except Exception as exc:  # noqa: BLE001 - monitor must be best-effort.
                self.status = "error"
                self.detail = str(exc)
                time.sleep(5)

    def _run_once(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.status = "unavailable"
            self.detail = "paho-mqtt n'est pas installé côté Raspberry."
            time.sleep(30)
            return

        settings = self.settings
        client = mqtt.Client(client_id=f"{settings.client_id}-monitor")

        def on_connect(mqtt_client, _userdata, _flags, return_code, *_args):
            if return_code != 0:
                self.status = "error"
                self.detail = f"Connexion MQTT refusée: {return_code}"
                return
            topic = f"{settings.base_topic.strip('/')}/#"
            mqtt_client.subscribe(topic, qos=settings.qos)
            self.status = "connected"
            self.detail = f"Abonné à {topic}"

        def on_message(_client, _userdata, message):
            self.record_message(message.topic, message.payload)

        client.on_connect = on_connect
        client.on_message = on_message
        if settings.username:
            client.username_pw_set(settings.username, settings.password)
        if settings.tls_enabled:
            client.tls_set()
        client.connect(settings.host, settings.port, settings.keepalive)
        client.loop_forever()


def _parse_slot_topic(topic: str) -> tuple[str, str] | None:
    """Return slot id and suffix from station/.../<slot>/<suffix> topics."""
    parts = [part for part in str(topic or "").strip("/").split("/") if part]
    if len(parts) < 3:
        return None
    suffix = parts[-1]
    slot_id = parts[-2]
    if not slot_id or not suffix:
        return None
    return slot_id, suffix


def _extract_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "on", "present", "closed"}:
        return True
    if normalized in {"false", "0", "no", "off", "absent", "open"}:
        return False
    return None


def build_slot_monitor() -> MqttSlotMonitor:
    """Factory used by the kiosk server."""
    return MqttSlotMonitor()


def publish_slot_command(slot_id: str, action: str, topic_prefix: str | None = None, **metadata: Any) -> dict[str, Any]:
    """Publish a command to one ESP32 slot through the local MQTT broker."""

    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("paho-mqtt n'est pas installé côté Raspberry.") from exc

    settings = MqttSettings()
    command_id = str(metadata.pop("command_id", "") or uuid.uuid4())
    action = action.upper()
    payload = {
        "command_id": command_id,
        "action": action,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    payload_errors = validate_command_payload(payload)
    if payload_errors:
        raise RuntimeError(f"Commande MQTT invalide: {'; '.join(payload_errors)}")

    command_topic = slot_topic(slot_id, settings=settings, topic_prefix=topic_prefix)
    ack_topic = slot_topic(slot_id, suffix="ack", settings=settings, topic_prefix=topic_prefix)
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

    client = mqtt.Client(client_id=f"{settings.client_id}-cmd-{uuid.uuid4().hex[:8]}")
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
        raise RuntimeError(f"Commande MQTT {action} refusée par ESP32 sur {ack_topic}{detail}.")

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
