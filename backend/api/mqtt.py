from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from django.conf import settings

from api.services.mqtt_tls import configure_mqtt_tls
from api.tasks import process_mqtt_message, process_mqtt_message_task

logger = logging.getLogger(__name__)


def _subscription_topic() -> str:
    """Return the supervision topic tree subscribed by the backend bridge."""
    base_topic = str(settings.MQTT_BASE_TOPIC or "station").strip("/")
    return f"{base_topic}/#" if base_topic else "#"


def _handle_message(topic: str, payload: bytes):
    """Dispatch one raw MQTT message to Celery or the local processor."""
    payload_text = payload.decode("utf-8", errors="replace")
    if process_mqtt_message_task is not None:
        process_mqtt_message_task.delay(topic, payload_text)
        return
    process_mqtt_message(topic, payload_text)


def _mqtt_connection_succeeded(reason_code) -> bool:
    """Return whether a paho MQTT connect code represents success."""
    normalized = str(reason_code).strip().lower()
    return reason_code == 0 or normalized in {"0", "success"}


def _write_bridge_heartbeat() -> None:
    """Persist a timestamp proving that the MQTT bridge is connected."""
    heartbeat_file = Path(settings.MQTT_BRIDGE_HEARTBEAT_FILE)
    heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_file.write_text(str(time.time()), encoding="utf-8")


def _start_bridge_heartbeat(connected_event: threading.Event) -> threading.Thread:
    """Start a background heartbeat writer while the MQTT bridge is connected."""

    def heartbeat_loop():
        while True:
            if connected_event.is_set():
                try:
                    _write_bridge_heartbeat()
                except OSError:
                    logger.exception("Impossible d'ecrire le heartbeat du bridge MQTT.")
            time.sleep(settings.MQTT_BRIDGE_HEARTBEAT_INTERVAL_SECONDS)

    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    thread.start()
    return thread


def _connect_with_retry(client) -> None:
    """Connect to the configured broker, waiting if the field broker is not ready yet."""
    retry_seconds = max(float(settings.MQTT_BRIDGE_CONNECT_RETRY_SECONDS), 1.0)
    while True:
        try:
            client.connect(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
            return
        except OSError as exc:
            logger.warning(
                "Bridge MQTT: impossible de joindre %s:%s (%s). Nouvelle tentative dans %.1fs.",
                settings.MQTT_HOST,
                settings.MQTT_PORT,
                exc,
                retry_seconds,
            )
            print(
                "MQTT bridge waiting for "
                f"{settings.MQTT_HOST}:{settings.MQTT_PORT}; retry in {retry_seconds:.1f}s",
                flush=True,
            )
            time.sleep(retry_seconds)


def run_mqtt_bridge():
    """Subscribe to ESP32 MQTT supervision topics and enqueue backend ingestion."""
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("Installe paho-mqtt pour lancer le bridge MQTT.") from exc

    topics = [(_subscription_topic(), settings.MQTT_QOS)]
    topic_label = ", ".join(topic for topic, _qos in topics)
    client = mqtt.Client(client_id=settings.MQTT_BACKEND_CLIENT_ID)
    connected_event = threading.Event()
    _start_bridge_heartbeat(connected_event)

    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    configure_mqtt_tls(client)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        logger.info("MQTT connecté à %s:%s code=%s", settings.MQTT_HOST, settings.MQTT_PORT, reason_code)
        if _mqtt_connection_succeeded(reason_code):
            connected_event.set()
            _write_bridge_heartbeat()
        print(
            f"MQTT bridge connected to {settings.MQTT_HOST}:{settings.MQTT_PORT} "
            f"code={reason_code}; subscribing to {topic_label}",
            flush=True,
        )
        client.subscribe(topics)

    def on_message(client, userdata, message):
        logger.debug("MQTT message topic=%s payload=%s", message.topic, message.payload)
        print(f"MQTT bridge received {message.topic}", flush=True)
        _handle_message(message.topic, message.payload)

    def on_disconnect(client, userdata, *args):
        reason_code = args[1] if len(args) >= 2 else args[0] if args else "unknown"
        connected_event.clear()
        logger.warning("MQTT deconnecte de %s:%s code=%s", settings.MQTT_HOST, settings.MQTT_PORT, reason_code)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    _connect_with_retry(client)
    client.loop_forever()
