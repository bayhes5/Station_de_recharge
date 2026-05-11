"""MicroPython firmware prototype for one charging slot ESP32.

The same file can be reused by the three physical slots by changing SLOT_ID.
It publishes telemetry to MQTT and listens for backend/Raspberry commands.
"""

import time
import ujson
import network
from machine import I2C, Pin
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
DHT_PIN = 4
INA219_SDA_PIN = 21
INA219_SCL_PIN = 25
INA219_ADDRESS = 0x40
INA219_SHUNT_OHMS = 0.1

TELEMETRY_INTERVAL_SECONDS = 2
MAX_CURRENT_A = 3.0
MAX_TEMPERATURE_C = 50.0
SIMULATE_SENSORS_ON_ERROR = True


hall = Pin(HALL_PIN, Pin.IN, Pin.PULL_UP)
door = Pin(DOOR_PIN, Pin.IN, Pin.PULL_UP)
lock = Pin(LOCK_PIN, Pin.OUT)
charge_relay = Pin(CHARGE_PIN, Pin.OUT)

state = "idle"
session_id = ""
last_telemetry = 0
last_environment = {"read_at": -999, "temperature": None, "humidity": None}
last_power_sample = {"read_at": -999, "current": None, "voltage": None, "power": None}


def topic(suffix):
    """Build an MQTT topic for this slot."""
    return "{}/{}/{}".format(MQTT_BASE_TOPIC, SLOT_ID, suffix)


TOPIC_CMD = topic("cmd")
TOPIC_ACK = topic("ack")
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


def init_dht22():
    """Initialize the DHT22 if the MicroPython module is available."""
    try:
        from dht import DHT22 as Dht22Sensor
    except ImportError:
        print("DHT module not available; using simulated environment values.")
        return None
    try:
        return Dht22Sensor(Pin(DHT_PIN))
    except Exception as exc:
        print("DHT22 init failed:", exc)
        return None


def init_ina219():
    """Initialize the INA219 I2C bus if the sensor answers."""
    try:
        bus = I2C(0, sda=Pin(INA219_SDA_PIN), scl=Pin(INA219_SCL_PIN), freq=400000)
        if INA219_ADDRESS not in bus.scan():
            print("INA219 not found on I2C; using simulated electrical values.")
            return None
        return bus
    except Exception as exc:
        print("INA219 init failed:", exc)
        return None


def read_u16_register(i2c, address, register):
    """Read one big-endian 16-bit register."""
    data = i2c.readfrom_mem(address, register, 2)
    return (data[0] << 8) | data[1]


def signed_16(value):
    """Convert a raw 16-bit value to signed integer."""
    return value - 65536 if value & 0x8000 else value


def simulated_current_a():
    """Return a simulated current when INA219 is absent."""
    return 1.2 if state == "charging" else 0.0


def simulated_voltage_v():
    """Return a simulated voltage when INA219 is absent."""
    return 41.5 if state == "charging" else 0.0


def simulated_temperature_c():
    """Return a simulated temperature when DHT22 is absent."""
    return 28.0


def simulated_humidity_percent():
    """Return a simulated humidity when DHT22 is absent."""
    return 45.0


def read_environment():
    """Return cached DHT22 temperature/humidity, with simulation fallback."""
    global last_environment

    now = time.time()
    if now - last_environment["read_at"] < 2 and last_environment["temperature"] is not None:
        return last_environment

    if dht_sensor is not None:
        try:
            dht_sensor.measure()
            last_environment = {
                "read_at": now,
                "temperature": float(dht_sensor.temperature()),
                "humidity": float(dht_sensor.humidity()),
            }
            return last_environment
        except Exception as exc:
            print("DHT22 read failed:", exc)

    if last_environment["temperature"] is not None and not SIMULATE_SENSORS_ON_ERROR:
        return last_environment

    last_environment = {
        "read_at": now,
        "temperature": simulated_temperature_c(),
        "humidity": simulated_humidity_percent(),
    }
    return last_environment


def read_power_sample():
    """Return cached INA219 current/voltage/power, with simulation fallback."""
    global last_power_sample

    now = time.time()
    if now - last_power_sample["read_at"] < 1 and last_power_sample["current"] is not None:
        return last_power_sample

    if ina219_i2c is not None:
        try:
            shunt_raw = signed_16(read_u16_register(ina219_i2c, INA219_ADDRESS, 0x01))
            bus_raw = read_u16_register(ina219_i2c, INA219_ADDRESS, 0x02)
            voltage = ((bus_raw >> 3) * 0.004)
            current = (shunt_raw * 0.00001) / INA219_SHUNT_OHMS
            power = voltage * current
            last_power_sample = {
                "read_at": now,
                "current": current,
                "voltage": voltage,
                "power": power,
            }
            return last_power_sample
        except Exception as exc:
            print("INA219 read failed:", exc)

    if last_power_sample["current"] is not None and not SIMULATE_SENSORS_ON_ERROR:
        return last_power_sample

    voltage = simulated_voltage_v()
    current = simulated_current_a()
    last_power_sample = {
        "read_at": now,
        "current": current,
        "voltage": voltage,
        "power": voltage * current,
    }
    return last_power_sample


def read_current_a():
    """Return current measured by INA219, or a simulated value."""
    return read_power_sample()["current"]


def read_voltage_v():
    """Return voltage measured by INA219, or a simulated value."""
    return read_power_sample()["voltage"]


def read_temperature_c():
    """Return temperature measured by DHT22, or a simulated value."""
    return read_environment()["temperature"]


def read_humidity_percent():
    """Return humidity measured by DHT22, or a simulated value."""
    return read_environment()["humidity"]


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


def publish_ack(client, payload, status, message=""):
    """Confirm command execution to the Raspberry kiosk."""
    publish_json(
        client,
        TOPIC_ACK,
        {
            "command_id": payload.get("command_id") or "",
            "action": str(payload.get("action") or "").upper(),
            "status": status,
            "message": message,
            "state": state,
            "slot_id": SLOT_ID,
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
        publish_ack(mqtt_client, payload, "accepted", "Emplacement reserve.")
    elif action == "STOP":
        handle_stop(mqtt_client)
        publish_ack(mqtt_client, payload, "stopped", "Charge arretee.")
    elif action == "LOCK":
        lock_slot()
        publish_status(mqtt_client, "locked")
        publish_ack(mqtt_client, payload, "locked", "Boitier verrouille.")
    elif action == "UNLOCK":
        unlock_slot()
        publish_status(mqtt_client, "unlocked")
        publish_ack(mqtt_client, payload, "unlocked", "Boitier deverrouille.")
    else:
        publish_ack(mqtt_client, payload, "error", "Commande inconnue.")


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
    power_sample = read_power_sample()
    environment = read_environment()
    payload = {
        "slot_id": SLOT_ID,
        "session_id": session_id,
        "state": state,
        "current": power_sample["current"],
        "voltage": power_sample["voltage"],
        "power": power_sample["power"],
        "energy_kwh": 0.0,
        "temperature": environment["temperature"],
        "humidity": environment["humidity"],
        "door": read_door_closed(),
        "cable": read_cable_present(),
    }
    publish_json(client, TOPIC_TELEMETRY, payload)


dht_sensor = init_dht22()
ina219_i2c = init_ina219()

connect_wifi()
mqtt_client = connect_mqtt()
stop_charge()
lock_slot()
publish_status(mqtt_client, "boot")

while True:
    mqtt_client.check_msg()
    update_state(mqtt_client)

    now = time.time()
    if now - last_telemetry >= TELEMETRY_INTERVAL_SECONDS:
        publish_telemetry(mqtt_client)
        last_telemetry = now

    time.sleep(0.2)
