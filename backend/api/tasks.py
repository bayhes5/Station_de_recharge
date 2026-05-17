from __future__ import annotations

import json
import logging

from django.conf import settings

from api.realtime import broadcast_supervision_update
from api.services.telemetry import ingest_slot_ack, ingest_slot_status, ingest_slot_telemetry

logger = logging.getLogger(__name__)

SUPPORTED_MQTT_MESSAGE_KINDS = {"ack", "alert", "status", "telemetry"}


def _topic_parts(topic: str) -> list[str]:
    """Return normalized MQTT topic parts."""
    return [part for part in topic.split("/") if part]


def _extract_slot_id(topic: str) -> str:
    """Extract the slot identifier from an ESP32 MQTT topic."""
    parts = _topic_parts(topic)
    if len(parts) >= 2 and parts[-1] in SUPPORTED_MQTT_MESSAGE_KINDS:
        return parts[-2]
    return "unknown"


def _extract_message_kind(topic: str) -> str:
    """Return the semantic MQTT message kind from the topic suffix."""
    parts = _topic_parts(topic)
    message_kind = parts[-1] if parts else ""
    return message_kind if message_kind in SUPPORTED_MQTT_MESSAGE_KINDS else ""


def _strip_base_topic(prefix_parts: list[str]) -> list[str]:
    """Remove the configured MQTT base topic from a structured topic prefix."""
    base_parts = _topic_parts(getattr(settings, "MQTT_BASE_TOPIC", "station"))
    if base_parts and prefix_parts[: len(base_parts)] == base_parts:
        return prefix_parts[len(base_parts) :]
    return prefix_parts


def _extract_topic_prefix(topic: str) -> str:
    """Return the station/borne prefix found before the slot id, if any."""
    parts = _topic_parts(topic)
    if len(parts) < 3 or parts[-1] not in SUPPORTED_MQTT_MESSAGE_KINDS:
        return ""
    prefix_parts = _strip_base_topic(parts[:-2])
    return "/".join(prefix_parts)


def process_mqtt_message(topic: str, payload: str | bytes):
    """Process one MQTT message synchronously for local/dev usage."""
    raw_payload = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError:
        logger.warning("MQTT payload ignore: JSON invalide sur %s: %s", topic, raw_payload)
        return None

    message_kind = _extract_message_kind(topic)
    if not message_kind:
        logger.debug("MQTT payload ignore: topic non supervise %s", topic)
        return None

    slot_id = str(data.pop("slot_id", "") or _extract_slot_id(topic))
    topic_prefix = _extract_topic_prefix(topic)
    if message_kind == "ack":
        result = ingest_slot_ack(slot_id=slot_id, payload=data, topic_prefix=topic_prefix)
        logger.info(
            "MQTT ACK ingere prefix=%s slot=%s action=%s status=%s command_id=%s",
            topic_prefix,
            slot_id,
            result.action,
            result.status,
            result.command_id,
        )
        response = {
            "slot_id": slot_id,
            "topic_prefix": topic_prefix,
            "message_type": "ack",
            "device_status": result.device.status,
            "last_seen": result.device.last_seen.isoformat() if result.device.last_seen else None,
            "command_id": result.command_id,
            "command_action": result.action,
            "command_status": result.status,
            "capteur_count": 0,
            "alert_count": 0,
            "session_telemetry_created": False,
        }
        broadcast_supervision_update("mqtt-ack", response)
        return response

    if message_kind == "status":
        result = ingest_slot_status(slot_id=slot_id, payload=data, topic_prefix=topic_prefix)
        logger.info("MQTT status ingere prefix=%s slot=%s status=%s", topic_prefix, slot_id, result.device.status)
        response = {
            "slot_id": slot_id,
            "topic_prefix": topic_prefix,
            "message_type": "status",
            "device_status": result.device.status,
            "last_seen": result.device.last_seen.isoformat() if result.device.last_seen else None,
            "capteur_count": 0,
            "alert_count": 0,
            "session_telemetry_created": False,
        }
        broadcast_supervision_update("mqtt-status", response)
        return response

    if message_kind == "alert":
        data.setdefault("state", "error")
        result = ingest_slot_telemetry(slot_id=slot_id, payload=data, topic_prefix=topic_prefix)
        logger.warning("MQTT alert ingeree prefix=%s slot=%s alerts=%s", topic_prefix, slot_id, result.alert_count)
        response = {
            "slot_id": slot_id,
            "topic_prefix": topic_prefix,
            "message_type": "alert",
            "capteur_count": result.capteur_count,
            "alert_count": result.alert_count,
            "session_telemetry_created": result.session_telemetry_created,
        }
        broadcast_supervision_update("mqtt-alert", response)
        return response

    result = ingest_slot_telemetry(slot_id=slot_id, payload=data, topic_prefix=topic_prefix)
    logger.info(
        "MQTT telemetry ingeree prefix=%s slot=%s sensors=%s alerts=%s session=%s",
        topic_prefix,
        slot_id,
        result.capteur_count,
        result.alert_count,
        result.session_telemetry_created,
    )
    response = {
        "slot_id": slot_id,
        "topic_prefix": topic_prefix,
        "message_type": "telemetry",
        "capteur_count": result.capteur_count,
        "alert_count": result.alert_count,
        "session_telemetry_created": result.session_telemetry_created,
    }
    broadcast_supervision_update("mqtt-telemetry", response)
    return response


try:
    from config.celery import app as celery_app
except ImportError:
    celery_app = None


if celery_app:

    @celery_app.task(name="api.process_mqtt_message")
    def process_mqtt_message_task(topic: str, payload: str):
        """Celery entrypoint used by the MQTT bridge in production."""
        return process_mqtt_message(topic, payload)

else:
    process_mqtt_message_task = None
