from __future__ import annotations

import json
import logging

from django.conf import settings

from api.realtime import broadcast_supervision_update
from api.services.telemetry import ingest_slot_status, ingest_slot_telemetry

logger = logging.getLogger(__name__)


def _extract_slot_id(topic: str) -> str:
    """Extract the slot identifier from an ESP32 MQTT topic."""
    parts = [part for part in topic.split("/") if part]
    if len(parts) >= 2 and parts[0] == settings.MQTT_BASE_TOPIC:
        return parts[1]
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"


def _extract_message_kind(topic: str) -> str:
    """Return the semantic MQTT message kind from the topic suffix."""
    parts = [part for part in topic.split("/") if part]
    return parts[-1] if parts else "telemetry"


def process_mqtt_message(topic: str, payload: str | bytes):
    """Process one MQTT message synchronously for local/dev usage."""
    raw_payload = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError:
        logger.warning("MQTT payload ignore: JSON invalide sur %s: %s", topic, raw_payload)
        return None

    slot_id = str(data.pop("slot_id", "") or _extract_slot_id(topic))
    message_kind = _extract_message_kind(topic)
    if message_kind == "status":
        result = ingest_slot_status(slot_id=slot_id, payload=data)
        logger.info("MQTT status ingere slot=%s status=%s", slot_id, result.device.status)
        response = {
            "slot_id": slot_id,
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
        result = ingest_slot_telemetry(slot_id=slot_id, payload=data)
        logger.warning("MQTT alert ingeree slot=%s alerts=%s", slot_id, result.alert_count)
        response = {
            "slot_id": slot_id,
            "message_type": "alert",
            "capteur_count": result.capteur_count,
            "alert_count": result.alert_count,
            "session_telemetry_created": result.session_telemetry_created,
        }
        broadcast_supervision_update("mqtt-alert", response)
        return response

    result = ingest_slot_telemetry(slot_id=slot_id, payload=data)
    logger.info(
        "MQTT telemetry ingeree slot=%s sensors=%s alerts=%s session=%s",
        slot_id,
        result.capteur_count,
        result.alert_count,
        result.session_telemetry_created,
    )
    response = {
        "slot_id": slot_id,
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
