"""MicroPython firmware prototype for one charging slot ESP32.

The same file can be reused by the three physical slots by changing SLOT_ID.
It publishes telemetry to MQTT and listens for backend/Raspberry commands.
"""

import time
import ujson
import network
from machine import Pin
from umqtt.simple import MQTTClient


WIFI_SSID = "WIFI_SSID"
WIFI_PASSWORD = "WIFI_PASSWORD"

MQTT_HOST = "192.168.1.10"
MQTT_PORT = 1883
MQTT_USER = None
MQTT_PASSWORD = None
MQTT_BASE_TOPIC = "station"
SLOT_ID = "slot1"
CLIENT_ID = "esp32-slot1"

HALL_PIN = 19
DOOR_PIN = 18
LOCK_PIN = 23
CHARGE_PIN = 22

TELEMETRY_INTERVAL_SECONDS = 2
MAX_CURRENT_A = 3.0
MAX_TEMPERATURE_C = 50.0


hall = Pin(HALL_PIN, Pin.IN, Pin.PULL_UP)
door = Pin(DOOR_PIN, Pin.IN, Pin.PULL_UP)
lock = Pin(LOCK_PIN, Pin.OUT)
charge_relay = Pin(CHARGE_PIN, Pin.OUT)

state = "idle"
session_id = ""
last_telemetry = 0


def topic(suffix):
    """Build an MQTT topic for this slot."""
    return "{}/{}/{}".format(MQTT_BASE_TOPIC, SLOT_ID, suffix)


TOPIC_CMD = topic("cmd")
TOPIC_STATUS = topic("status")
TOPIC_ALERT = topic("alert")
TOPIC_TELEMETRY = topic("telemetry")


def connect_wifi():
    """Connect the ESP32 to WiFi."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan

    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while not wlan.isconnected():
        time.sleep(1)
    return wlan


def read_cable_present():
    """Return True when the Hall sensor sees the charging cable."""
    return hall.value() == 0


def read_door_closed():
    """Return True when the enclosure contact reports closed."""
    return door.value() == 0


def read_current_a():
    """Return simulated current until the INA219 driver is wired."""
    return 1.2 if state == "charging" else 0.0


def read_voltage_v():
    """Return simulated voltage until the INA219 driver is wired."""
    return 12.0 if state == "charging" else 0.0


def read_temperature_c():
    """Return simulated temperature until the DHT/BME sensor is wired."""
    return 28.0


def lock_slot():
    """Lock the enclosure."""
    lock.value(1)


def unlock_slot():
    """Unlock the enclosure."""
    lock.value(0)


def start_charge():
    """Enable the simulated charge relay."""
    charge_relay.value(1)


def stop_charge():
    """Disable the simulated charge relay."""
    charge_relay.value(0)


def publish_json(client, mqtt_topic, payload):
    """Publish a JSON payload."""
    client.publish(mqtt_topic, ujson.dumps(payload))


def publish_status(client, event, reason=""):
    """Publish one status event."""
    publish_json(
        client,
        TOPIC_STATUS,
        {
            "slot_id": SLOT_ID,
            "event": event,
            "reason": reason,
            "state": state,
            "session_id": session_id,
        },
    )


def stop_session(client, reason):
    """Stop charge and report an alert/status event."""
    global state

    stop_charge()
    unlock_slot()
    state = "idle"
    publish_json(
        client,
        TOPIC_ALERT,
        {
            "slot_id": SLOT_ID,
            "type": reason,
            "state": "error",
            "session_id": session_id,
        },
    )
    publish_status(client, "stopped", reason)


def handle_start(client, payload):
    """Accept a START command and wait for physical conditions."""
    global state, session_id

    session_id = payload.get("session_id") or ""
    unlock_slot()
    stop_charge()
    state = "reserved"
    publish_status(client, "reserved")


def handle_stop(client, reason="remote_stop"):
    """Accept a STOP command."""
    stop_session(client, reason)


def on_message(topic_bytes, message):
    """Handle backend/Raspberry commands."""
    try:
        payload = ujson.loads(message)
    except ValueError:
        payload = {"action": message.decode().upper()}

    action = str(payload.get("action", "")).upper()
    if action == "START":
        handle_start(mqtt_client, payload)
    elif action == "STOP":
        handle_stop(mqtt_client)
    elif action == "LOCK":
        lock_slot()
        publish_status(mqtt_client, "locked")
    elif action == "UNLOCK":
        unlock_slot()
        publish_status(mqtt_client, "unlocked")


def connect_mqtt():
    """Connect and subscribe to command topic."""
    client = MQTTClient(
        CLIENT_ID,
        MQTT_HOST,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=60,
    )
    client.set_callback(on_message)
    client.connect()
    client.subscribe(TOPIC_CMD)
    return client


def update_state(client):
    """Run the local slot state machine."""
    global state

    cable = read_cable_present()
    door_closed = read_door_closed()
    current = read_current_a()
    temperature = read_temperature_c()

    if state == "reserved" and cable and door_closed:
        lock_slot()
        start_charge()
        state = "charging"
        publish_status(client, "charging_started")

    if state == "charging":
        if not door_closed:
            stop_session(client, "intrusion")
        elif not cable:
            stop_session(client, "cable_removed")
        elif current > MAX_CURRENT_A:
            stop_session(client, "overcurrent")
        elif temperature > MAX_TEMPERATURE_C:
            stop_session(client, "overheat")


def publish_telemetry(client):
    """Publish the current telemetry sample."""
    payload = {
        "slot_id": SLOT_ID,
        "session_id": session_id,
        "state": state,
        "current": read_current_a(),
        "voltage": read_voltage_v(),
        "energy_kwh": 0.0,
        "temperature": read_temperature_c(),
        "humidity": 45.0,
        "door": read_door_closed(),
        "cable": read_cable_present(),
    }
    publish_json(client, TOPIC_TELEMETRY, payload)


connect_wifi()
mqtt_client = connect_mqtt()
unlock_slot()
stop_charge()
publish_status(mqtt_client, "boot")

while True:
    mqtt_client.check_msg()
    update_state(mqtt_client)

    now = time.time()
    if now - last_telemetry >= TELEMETRY_INTERVAL_SECONDS:
        publish_telemetry(mqtt_client)
        last_telemetry = now

    time.sleep(0.2)
