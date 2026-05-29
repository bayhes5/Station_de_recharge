"""Wokwi MicroPython simulation for MQTT telemetry.

Use this simulation to validate the end-to-end flow:
Wokwi ESP32 -> MQTT broker -> backend bridge -> database -> Grafana.
"""

import time
import ujson
import network
from machine import ADC, Pin
from umqtt.simple import MQTTClient


WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

# For a browser-based Wokwi simulation, a public broker is the easiest option.
# To use the local Docker broker, expose it through a reachable LAN/tunnel address.
MQTT_HOST = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_BASE_TOPIC = "station"
SLOT_ID = "slot1"
CLIENT_ID = "wokwi-slot1"
FIRMWARE_VERSION = "1.0.0-wokwi"

HALL_PIN = 19
DOOR_PIN = 18
LOCK_PIN = 23
CHARGE_PIN = 22
CURRENT_ADC_PIN = 34
TEMPERATURE_ADC_PIN = 35

MAX_CURRENT_A = 3.0
MAX_TEMPERATURE_C = 50.0
TELEMETRY_INTERVAL_SECONDS = 2


cable_switch = Pin(HALL_PIN, Pin.IN, Pin.PULL_UP)
door_switch = Pin(DOOR_PIN, Pin.IN, Pin.PULL_UP)
lock_led = Pin(LOCK_PIN, Pin.OUT)
charge_led = Pin(CHARGE_PIN, Pin.OUT)
current_adc = ADC(Pin(CURRENT_ADC_PIN))
temperature_adc = ADC(Pin(TEMPERATURE_ADC_PIN))
current_adc.atten(ADC.ATTN_11DB)
temperature_adc.atten(ADC.ATTN_11DB)

state = "idle"
session_id = ""
last_telemetry = 0


def topic(suffix):
    """Build one MQTT topic for this simulated slot."""
    return "{}/{}/{}".format(MQTT_BASE_TOPIC, SLOT_ID, suffix)


TOPIC_CMD = topic("cmd")
TOPIC_ACK = topic("ack")
TOPIC_STATUS = topic("status")
TOPIC_ALERT = topic("alert")
TOPIC_TELEMETRY = topic("telemetry")


def connect_wifi():
    """Connect Wokwi ESP32 to its built-in WiFi network."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while not wlan.isconnected():
        print("Connexion WiFi Wokwi...")
        time.sleep(1)
    print("WiFi OK", wlan.ifconfig())


def format_mac(mac_bytes):
    """Return a colon-separated MAC address from MicroPython bytes."""
    return ":".join("{:02X}".format(value) for value in mac_bytes)


def device_identity():
    """Return simulated ESP32 inventory fields for MQTT payloads."""
    wlan = network.WLAN(network.STA_IF)
    ip_address = ""
    hardware_mac = ""
    try:
        if wlan.isconnected():
            ip_address = wlan.ifconfig()[0]
    except Exception:
        ip_address = ""
    try:
        hardware_mac = format_mac(wlan.config("mac"))
    except Exception:
        hardware_mac = ""
    return {
        "client_id": CLIENT_ID,
        "firmware_version": FIRMWARE_VERSION,
        "hardware_mac": hardware_mac,
        "ip_address": ip_address,
    }


def adc_ratio(adc):
    """Convert ADC reading to a 0..1 ratio."""
    return adc.read() / 4095


def read_cable_present():
    """Return True when the cable switch is active."""
    return cable_switch.value() == 0


def read_door_closed():
    """Return True when the enclosure switch is closed."""
    return door_switch.value() == 0


def read_current_a():
    """Map potentiometer to 0..4 A."""
    if state != "charging":
        return 0.0
    return round(adc_ratio(current_adc) * 4.0, 2)


def read_voltage_v():
    """Return simulated charging voltage."""
    return 12.0 if state == "charging" else 0.0


def read_temperature_c():
    """Map potentiometer to 20..70 C."""
    return round(20.0 + adc_ratio(temperature_adc) * 50.0, 1)


def publish_json(client, mqtt_topic, payload):
    """Publish a JSON MQTT message and print it for Wokwi logs."""
    encoded = ujson.dumps(payload)
    client.publish(mqtt_topic, encoded)
    print(mqtt_topic, encoded)


def publish_status(client, event, reason=""):
    """Publish one status event."""
    payload = {
        "slot_id": SLOT_ID,
        "event": event,
        "reason": reason,
        "state": state,
        "session_id": session_id,
    }
    payload.update(device_identity())
    publish_json(
        client,
        TOPIC_STATUS,
        payload,
    )


def publish_ack(client, payload, status, message=""):
    """Confirm command execution to the Raspberry kiosk."""
    ack_payload = {
        "command_id": payload.get("command_id") or "",
        "action": str(payload.get("action") or "").upper(),
        "status": status,
        "message": message,
        "state": state,
        "slot_id": SLOT_ID,
        "session_id": session_id,
    }
    ack_payload.update(device_identity())
    publish_json(
        client,
        TOPIC_ACK,
        ack_payload,
    )


def stop_session(client, reason):
    """Stop charging and publish an alert."""
    global state
    charge_led.value(0)
    lock_led.value(0)
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
    """Move slot to reserved state after a START command."""
    global state, session_id
    session_id = payload.get("session_id") or "wokwi-demo"
    state = "reserved"
    lock_led.value(0)
    charge_led.value(0)
    publish_status(client, "reserved")


def on_message(topic_bytes, message):
    """Handle MQTT command payloads."""
    try:
        payload = ujson.loads(message)
    except ValueError:
        payload = {"action": message.decode().upper()}

    action = str(payload.get("action", "")).upper()
    if action == "START":
        handle_start(mqtt_client, payload)
        publish_ack(mqtt_client, payload, "accepted", "Emplacement réservé.")
    elif action == "STOP":
        stop_session(mqtt_client, "remote_stop")
        publish_ack(mqtt_client, payload, "stopped", "Charge arrêtée.")
    elif action == "LOCK":
        lock_led.value(1)
        publish_status(mqtt_client, "locked")
        publish_ack(mqtt_client, payload, "locked", "Boitier verrouille.")
    elif action == "UNLOCK":
        lock_led.value(0)
        publish_status(mqtt_client, "unlocked")
        publish_ack(mqtt_client, payload, "unlocked", "Boitier deverrouille.")
    else:
        publish_ack(mqtt_client, payload, "error", "Commande inconnue.")


def connect_mqtt():
    """Connect to MQTT broker and subscribe to commands."""
    client = MQTTClient(CLIENT_ID, MQTT_HOST, port=MQTT_PORT, keepalive=60)
    client.set_callback(on_message)
    client.connect()
    client.subscribe(TOPIC_CMD)
    print("MQTT OK", MQTT_HOST, TOPIC_CMD)
    return client


def update_state(client):
    """Run the simulated slot state machine."""
    global state
    cable = read_cable_present()
    door_closed = read_door_closed()
    current = read_current_a()
    temperature = read_temperature_c()

    if state == "reserved" and cable and door_closed:
        state = "charging"
        lock_led.value(1)
        charge_led.value(1)
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
    """Publish one telemetry sample."""
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
    payload.update(device_identity())
    publish_json(
        client,
        TOPIC_TELEMETRY,
        payload,
    )


connect_wifi()
mqtt_client = connect_mqtt()
publish_status(mqtt_client, "boot")

while True:
    mqtt_client.check_msg()
    update_state(mqtt_client)

    now = time.time()
    if now - last_telemetry >= TELEMETRY_INTERVAL_SECONDS:
        publish_telemetry(mqtt_client)
        last_telemetry = now

    time.sleep(0.2)
