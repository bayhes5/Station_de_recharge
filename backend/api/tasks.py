from __future__ import annotations

import json
import logging

from django.conf import settings

from api.services.telemetry import ingest_slot_telemetry

logger = logging.getLogger(__name__)


def _extract_slot_id(topic: str) -> str:
    """Extract the slot identifier from a telemetry MQTT topic."""
    parts = [part for part in topic.split("/") if part]
    if len(parts) >= 2 and parts[0] == settings.MQTT_BASE_TOPIC:
        return parts[1]
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"


def process_mqtt_message(topic: str, payload: str | bytes):
    """Process one MQTT message synchronously for local/dev usage."""
    raw_payload = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError:
        logger.warning("MQTT payload ignore: JSON invalide sur %s: %s", topic, raw_payload)
        return None

    slot_id = str(data.pop("slot_id", "") or _extract_slot_id(topic))
    result = ingest_slot_telemetry(slot_id=slot_id, payload=data)
    logger.info(
        "MQTT telemetry ingeree slot=%s sensors=%s alerts=%s session=%s",
        slot_id,
        result.capteur_count,
        result.alert_count,
        result.session_telemetry_created,
    )
    return {
        "slot_id": slot_id,
        "capteur_count": result.capteur_count,
        "alert_count": result.alert_count,
        "session_telemetry_created": result.session_telemetry_created,
    }


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
