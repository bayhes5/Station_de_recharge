from __future__ import annotations

import logging

from django.conf import settings

from api.tasks import process_mqtt_message, process_mqtt_message_task

logger = logging.getLogger(__name__)


def _handle_message(topic: str, payload: bytes):
    payload_text = payload.decode("utf-8", errors="replace")
    if process_mqtt_message_task is not None:
        process_mqtt_message_task.delay(topic, payload_text)
        return
    process_mqtt_message(topic, payload_text)


def run_mqtt_bridge():
    """Subscribe to ESP32 MQTT telemetry and enqueue backend ingestion."""
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("Installe paho-mqtt pour lancer le bridge MQTT.") from exc

    topic = f"{settings.MQTT_BASE_TOPIC}/+/telemetry"
    client = mqtt.Client(client_id=settings.MQTT_BACKEND_CLIENT_ID)

    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    if settings.MQTT_TLS_ENABLED:
        client.tls_set()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        logger.info("MQTT connecte a %s:%s code=%s", settings.MQTT_HOST, settings.MQTT_PORT, reason_code)
        client.subscribe(topic, qos=settings.MQTT_QOS)

    def on_message(client, userdata, message):
        logger.debug("MQTT message topic=%s payload=%s", message.topic, message.payload)
        _handle_message(message.topic, message.payload)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
    client.loop_forever()
