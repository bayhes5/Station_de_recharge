import importlib
import json
import sys
import types
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "app"


class FakePublishResult:
    def wait_for_publish(self, timeout=None):
        return True


class FakeMqttClient:
    ack_payload = None
    instances = []

    def __init__(self, client_id):
        self.client_id = client_id
        self.on_message = None
        self.on_subscribe = None
        self.username = None
        self.password = None
        self.subscriptions = []
        self.published = []
        FakeMqttClient.instances.append(self)

    def username_pw_set(self, username, password):
        self.username = username
        self.password = password

    def tls_set(self):
        self.tls_enabled = True

    def connect(self, host, port, keepalive):
        self.host = host
        self.port = port
        self.keepalive = keepalive

    def loop_start(self):
        self.loop_started = True

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))
        if self.on_subscribe:
            self.on_subscribe(self, None, None, None)

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        if FakeMqttClient.ack_payload is not None and self.on_message:
            message = types.SimpleNamespace(
                topic=self.subscriptions[-1][0],
                payload=json.dumps(FakeMqttClient.ack_payload).encode("utf-8"),
            )
            self.on_message(self, None, message)
        return FakePublishResult()

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.disconnected = True


def install_fake_paho(monkeypatch):
    FakeMqttClient.ack_payload = None
    FakeMqttClient.instances = []
    paho_module = types.ModuleType("paho")
    mqtt_package = types.ModuleType("paho.mqtt")
    client_module = types.ModuleType("paho.mqtt.client")
    client_module.Client = FakeMqttClient
    mqtt_package.client = client_module
    paho_module.mqtt = mqtt_package
    monkeypatch.setitem(sys.modules, "paho", paho_module)
    monkeypatch.setitem(sys.modules, "paho.mqtt", mqtt_package)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", client_module)


def load_mqtt_client(monkeypatch, ack_required="false"):
    monkeypatch.syspath_prepend(str(APP_DIR))
    monkeypatch.setenv("MQTT_HOST", "mqtt.local")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_BASE_TOPIC", "station")
    monkeypatch.setenv("MQTT_RASPBERRY_CLIENT_ID", "test-kiosk")
    monkeypatch.setenv("MQTT_QOS", "1")
    monkeypatch.setenv("MQTT_ACK_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("MQTT_ACK_REQUIRED", ack_required)
    sys.modules.pop("mqtt_client", None)
    return importlib.import_module("mqtt_client")


def test_publish_slot_command_allows_missing_ack_when_not_required(monkeypatch):
    install_fake_paho(monkeypatch)
    mqtt_client = load_mqtt_client(monkeypatch, ack_required="false")

    result = mqtt_client.publish_slot_command("slot1", "START", session_id="session-1")

    assert result["topic"] == "station/slot1/cmd"
    assert result["ack_topic"] == "station/slot1/ack"
    assert result["ack_required"] is False
    assert result["ack_received"] is False
    assert result["command"]["session_id"] == "session-1"


def test_publish_slot_command_rejects_missing_ack_when_required(monkeypatch):
    install_fake_paho(monkeypatch)
    mqtt_client = load_mqtt_client(monkeypatch, ack_required="true")

    with pytest.raises(RuntimeError, match="sans confirmation ESP32"):
        mqtt_client.publish_slot_command("slot1", "START")


def test_publish_slot_command_accepts_matching_ack_when_required(monkeypatch):
    install_fake_paho(monkeypatch)
    mqtt_client = load_mqtt_client(monkeypatch, ack_required="true")
    FakeMqttClient.ack_payload = {
        "command_id": "cmd-1",
        "action": "START",
        "status": "accepted",
    }

    result = mqtt_client.publish_slot_command("slot1", "START", command_id="cmd-1")

    assert result["ack_received"] is True
    assert result["ack"]["topic"] == "station/slot1/ack"
    assert result["ack"]["payload"]["status"] == "accepted"

