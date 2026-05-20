"""MicroPython firmware for one ESP32 charging slot.

This version is adapted for the current hardware test:
- DHT22 on GPIO25 for temperature and humidity.
- ESP32 identity fields: firmware version, IP address and MAC address.
- Current, voltage, door, cable, relay and lock are optional and disabled by
  default until wired.

It speaks the project MQTT contract:
station/<mqtt_prefix>/<slot_id>/cmd
station/<mqtt_prefix>/<slot_id>/ack
station/<mqtt_prefix>/<slot_id>/status
station/<mqtt_prefix>/<slot_id>/telemetry
station/<mqtt_prefix>/<slot_id>/alert
"""

import time
import ujson
import network
from machine import ADC, I2C, Pin
from umqtt.simple import MQTTClient


# ---------------------------------------------------------------------------
# Local configuration to adjust before flashing with Thonny.
# ---------------------------------------------------------------------------

WIFI_SSID = "WIFI_SSID"
WIFI_PASSWORD = "WIFI_PASSWORD"

# For local tests, use the Wi-Fi IP of the PC/Raspberry running Mosquitto.
MQTT_HOST = "192.168.1.10"
MQTT_PORT = 1883
MQTT_USER = None
MQTT_PASSWORD = None
MQTT_KEEPALIVE_SECONDS = 60
MQTT_BASE_TOPIC = "station"

# Must match the borne mqtt_prefix in the backend demo data.
# For the current demo this gives:
# station/station-demo/borne-1/slot1/telemetry
MQTT_TOPIC_PREFIX = "station-demo/borne-1"
SLOT_ID = "slot1"
CLIENT_ID = "esp32-station-demo-borne-1-slot1"
FIRMWARE_VERSION = "1.1.0-sensors"

# Only DHT22 and ESP32 identity are wired/reported for now.
PHYSICAL_INPUTS_ENABLED = False
OUTPUTS_ENABLED = False
SIMULATE_MISSING_SENSORS = False

# DHT22 prototype wiring from TEMPERATUREHUMIDY.txt.
DHT_PIN = 25

# Current prototype wiring from CURRENT.txt.
# This is an analog current sensor, not an INA219.
CURRENT_SENSOR_MODE = "none"  # "none" now, "adc" or "ina219" when wired.
ADC_CURRENT_PIN = 15
ADC_VREF = 3.3
ADC_RESOLUTION = 4095
ADC_ZERO_CURRENT_VOLTAGE = ADC_VREF / 2
ADC_SENSITIVITY_V_PER_A = 0.100
ADC_NOISE_FLOOR_A = 0.05

# Optional future INA219 wiring.
INA219_SDA_PIN = 21
INA219_SCL_PIN = 22
INA219_ADDRESS = 0x40
INA219_SHUNT_OHMS = 0.1

# Optional future physical wiring.
HALL_PIN = 19
DOOR_PIN = 18
LOCK_PIN = 23
CHARGE_RELAY_PIN = 22

TELEMETRY_ACTIVE_INTERVAL_SECONDS = 5
TELEMETRY_IDLE_INTERVAL_SECONDS = 30
STATUS_INTERVAL_SECONDS = 15
MAX_CURRENT_A = 3.0
MAX_TEMPERATURE_C = 50.0


state = "idle"
session_id = ""
last_telemetry_at = 0
last_status_at = 0
last_power_at = 0
energy_kwh = 0.0

dht_sensor = None
current_adc = None
ina219_i2c = None
hall = None
door = None
lock = None
charge_relay = None
mqtt_client = None
wlan = None


def normalized_topic_root():
    """Return the station/borne MQTT root used by this ESP32."""
    base = str(MQTT_BASE_TOPIC or "station").strip("/")
    prefix = str(MQTT_TOPIC_PREFIX or "").strip("/")
    if not prefix:
        return base
    if prefix == base or prefix.startswith(base + "/"):
        return prefix
    return "{}/{}".format(base, prefix)


def topic(suffix):
    """Build one MQTT topic for this slot."""
    return "{}/{}/{}".format(normalized_topic_root(), SLOT_ID, suffix)


TOPIC_CMD = topic("cmd")
TOPIC_ACK = topic("ack")
TOPIC_STATUS = topic("status")
TOPIC_ALERT = topic("alert")
TOPIC_TELEMETRY = topic("telemetry")


def now_seconds():
    """Return a monotonic-ish timestamp available on MicroPython."""
    return time.time()


def round_value(value, digits=3):
    """Round numeric telemetry while keeping None values readable."""
    if value is None:
        return None
    return round(float(value), digits)


def format_mac(mac_bytes):
    """Return a colon-separated MAC address from MicroPython bytes."""
    return ":".join("{:02X}".format(value) for value in mac_bytes)


def connect_wifi():
    """Connect to Wi-Fi and print the network identity."""
    station = network.WLAN(network.STA_IF)
    station.active(True)

    if not station.isconnected():
        print("Connecting to WiFi...")
        station.connect(WIFI_SSID, WIFI_PASSWORD)
        max_wait = 20
        while max_wait > 0 and not station.isconnected():
            max_wait -= 1
            time.sleep(1)

    if not station.isconnected():
        raise RuntimeError("WiFi connection failed")

    print("Connected to WiFi:", station.ifconfig())
    return station


def device_identity():
    """Return ESP32 identity fields ingested by the backend inventory."""
    ip_address = ""
    hardware_mac = ""
    try:
        if wlan and wlan.isconnected():
            ip_address = wlan.ifconfig()[0]
            hardware_mac = format_mac(wlan.config("mac"))
    except Exception as exc:
        print("Device identity read failed:", exc)

    return {
        "slot_id": SLOT_ID,
        "client_id": CLIENT_ID,
        "firmware_version": FIRMWARE_VERSION,
        "hardware_mac": hardware_mac,
        "ip_address": ip_address,
    }


def init_outputs():
    """Initialize optional relay outputs only when they are wired."""
    global lock, charge_relay
    if not OUTPUTS_ENABLED:
        print("Outputs disabled: lock and charge relay are not driven.")
        return
    lock = Pin(LOCK_PIN, Pin.OUT)
    charge_relay = Pin(CHARGE_RELAY_PIN, Pin.OUT)
    lock.value(1)
    charge_relay.value(0)


def init_physical_inputs():
    """Initialize optional door and cable inputs only when they are wired."""
    global hall, door
    if not PHYSICAL_INPUTS_ENABLED:
        print("Physical inputs disabled: cable and door are assumed valid.")
        return
    hall = Pin(HALL_PIN, Pin.IN, Pin.PULL_UP)
    door = Pin(DOOR_PIN, Pin.IN, Pin.PULL_UP)


def init_dht22():
    """Initialize DHT22 on the pin used by the colleague prototype."""
    try:
        from dht import DHT22
        sensor = DHT22(Pin(DHT_PIN))
        print("DHT22 ready on GPIO{}".format(DHT_PIN))
        return sensor
    except Exception as exc:
        print("DHT22 init failed:", exc)
        return None


def init_adc_current_sensor():
    """Initialize the analog current sensor used in CURRENT.txt."""
    try:
        adc = ADC(Pin(ADC_CURRENT_PIN))
        adc.atten(ADC.ATTN_11DB)
        try:
            adc.width(ADC.WIDTH_12BIT)
        except Exception as exc:
            print("ADC width configuration skipped:", exc)
        print("Analog current sensor ready on GPIO{}".format(ADC_CURRENT_PIN))
        return adc
    except Exception as exc:
        print("ADC current sensor init failed:", exc)
        return None


def init_ina219():
    """Initialize optional INA219 I2C mode for future wiring."""
    try:
        bus = I2C(0, sda=Pin(INA219_SDA_PIN), scl=Pin(INA219_SCL_PIN), freq=400000)
        if INA219_ADDRESS not in bus.scan():
            print("INA219 not found on I2C.")
            return None
        print("INA219 ready on I2C address 0x{:02X}".format(INA219_ADDRESS))
        return bus
    except Exception as exc:
        print("INA219 init failed:", exc)
        return None


def init_current_sensor():
    """Initialize the configured current sensor backend."""
    if CURRENT_SENSOR_MODE == "ina219":
        return None, init_ina219()
    if CURRENT_SENSOR_MODE == "adc":
        return init_adc_current_sensor(), None
    print("Current sensor disabled.")
    return None, None


def read_u16_register(i2c, address, register):
    """Read one big-endian 16-bit register."""
    data = i2c.readfrom_mem(address, register, 2)
    return (data[0] << 8) | data[1]


def signed_16(value):
    """Convert a raw 16-bit value to signed integer."""
    return value - 65536 if value & 0x8000 else value


def read_environment():
    """Read temperature and humidity from DHT22."""
    if dht_sensor is None:
        if SIMULATE_MISSING_SENSORS:
            return {"temperature": 28.0, "humidity": 45.0, "heat_index": 42.85}
        return {"temperature": None, "humidity": None, "heat_index": None}

    try:
        dht_sensor.measure()
        humidity = float(dht_sensor.humidity())
        temperature = float(dht_sensor.temperature())
        heat_index = temperature + 0.33 * humidity
        print(
            "Humidity: {}% Temperature: {:.1f}C Heat index: {:.1f}C".format(
                humidity,
                temperature,
                heat_index,
            )
        )
        if temperature > MAX_TEMPERATURE_C:
            print("ALERT temperature above {}C: {:.1f}C".format(MAX_TEMPERATURE_C, temperature))
        return {
            "temperature": temperature,
            "humidity": humidity,
            "heat_index": heat_index,
        }
    except Exception as exc:
        print("DHT22 read failed:", exc)
        if SIMULATE_MISSING_SENSORS:
            return {"temperature": 28.0, "humidity": 45.0, "heat_index": 42.85}
        return {"temperature": None, "humidity": None, "heat_index": None}


def read_adc_current():
    """Read current from the analog current sensor used by the prototype."""
    if current_adc is None:
        return None
    raw = current_adc.read()
    voltage = (raw / ADC_RESOLUTION) * ADC_VREF
    current = (voltage - ADC_ZERO_CURRENT_VOLTAGE) / ADC_SENSITIVITY_V_PER_A
    if abs(current) < ADC_NOISE_FLOOR_A:
        current = 0.0
    current = max(0.0, current)
    print("Current ADC raw={} voltage={:.3f}V current={:.2f}A".format(raw, voltage, current))
    return current


def read_ina219_power():
    """Read voltage/current/power from optional INA219 mode."""
    if ina219_i2c is None:
        return {"current": None, "voltage": None, "power": None}

    shunt_raw = signed_16(read_u16_register(ina219_i2c, INA219_ADDRESS, 0x01))
    bus_raw = read_u16_register(ina219_i2c, INA219_ADDRESS, 0x02)
    voltage = (bus_raw >> 3) * 0.004
    current = (shunt_raw * 0.00001) / INA219_SHUNT_OHMS
    current = max(0.0, current)
    return {"current": current, "voltage": voltage, "power": voltage * current}


def read_power_sample():
    """Read electrical telemetry in the shape expected by the backend."""
    if CURRENT_SENSOR_MODE == "ina219":
        sample = read_ina219_power()
        if sample["current"] is not None:
            return sample

    current = read_adc_current() if CURRENT_SENSOR_MODE == "adc" else None
    if current is None and CURRENT_SENSOR_MODE != "none" and SIMULATE_MISSING_SENSORS:
        current = 1.2 if state == "charging" else 0.0

    voltage = None
    power = None
    return {"current": current, "voltage": voltage, "power": power}


def read_cable_present():
    """Return cable state. Until wired, assume it is present for START tests."""
    if not PHYSICAL_INPUTS_ENABLED or hall is None:
        return True
    return hall.value() == 0


def read_door_closed():
    """Return door state. Until wired, assume it is closed for START tests."""
    if not PHYSICAL_INPUTS_ENABLED or door is None:
        return True
    return door.value() == 0


def reported_cable_present():
    """Return the cable telemetry value, or None when the sensor is not wired."""
    if not PHYSICAL_INPUTS_ENABLED or hall is None:
        return None
    return read_cable_present()


def reported_door_closed():
    """Return the door telemetry value, or None when the sensor is not wired."""
    if not PHYSICAL_INPUTS_ENABLED or door is None:
        return None
    return read_door_closed()


def lock_slot():
    """Lock the slot when the output is wired."""
    if lock is not None:
        lock.value(1)


def unlock_slot():
    """Unlock the slot when the output is wired."""
    if lock is not None:
        lock.value(0)


def start_charge_output():
    """Enable the charge relay when it is wired."""
    if charge_relay is not None:
        charge_relay.value(1)


def stop_charge_output():
    """Disable the charge relay when it is wired."""
    if charge_relay is not None:
        charge_relay.value(0)


def publish_json(client, mqtt_topic, payload):
    """Publish one JSON message on MQTT."""
    client.publish(mqtt_topic, ujson.dumps(payload))


def publish_status(client, event, reason=""):
    """Publish a status event consumed by the backend supervision bridge."""
    payload = {
        "event": event,
        "reason": reason,
        "state": state,
        "session_id": session_id,
        "door": reported_door_closed(),
        "cable": reported_cable_present(),
        "uptime_seconds": now_seconds(),
    }
    payload.update(device_identity())
    publish_json(client, TOPIC_STATUS, payload)


def publish_ack(client, command_payload, status, message=""):
    """Publish an ACK matching the Raspberry command_id/action contract."""
    payload = {
        "command_id": str(command_payload.get("command_id") or ""),
        "action": str(command_payload.get("action") or "").upper(),
        "status": status,
        "message": message,
        "state": state,
        "session_id": session_id or str(command_payload.get("session_id") or ""),
        "uptime_seconds": now_seconds(),
    }
    payload.update(device_identity())
    publish_json(client, TOPIC_ACK, payload)


def publish_alert(client, alert_type, message=""):
    """Publish a local safety alert."""
    payload = {
        "type": alert_type,
        "message": message,
        "state": "error",
        "session_id": session_id,
        "uptime_seconds": now_seconds(),
    }
    payload.update(device_identity())
    publish_json(client, TOPIC_ALERT, payload)


def accept_start(client, payload):
    """Accept START and move to charging for the current communication test."""
    global state, session_id

    if state == "charging" and session_id and payload.get("session_id") != session_id:
        publish_ack(client, payload, "denied", "Une charge est déjà active.")
        return

    session_id = str(payload.get("session_id") or "")
    unlock_slot()
    if read_cable_present() and read_door_closed():
        start_charge_output()
        lock_slot()
        state = "charging"
        publish_status(client, "charging_started")
        publish_ack(client, payload, "charging", "Charge démarrée.")
        publish_telemetry_now(client)
    else:
        stop_charge_output()
        state = "waiting_plug"
        publish_status(client, "waiting_plug")
        publish_ack(client, payload, "accepted", "En attente du câble et du boîtier.")
        publish_telemetry_now(client)


def accept_stop(client, payload, reason="remote_stop"):
    """Accept STOP and move back to idle."""
    global state, session_id

    stop_charge_output()
    unlock_slot()
    state = "idle"
    publish_status(client, "stopped", reason)
    publish_ack(client, payload, "stopped", "Charge arrêtée.")
    publish_telemetry_now(client)
    session_id = ""


def handle_command(topic_bytes, message):
    """Handle commands received from Raspberry over MQTT."""
    try:
        payload = ujson.loads(message)
    except ValueError:
        payload = {"action": message.decode().upper()}

    action = str(payload.get("action") or "").upper()
    print("MQTT command received:", action, payload)

    if action == "START":
        accept_start(mqtt_client, payload)
    elif action == "STOP":
        accept_stop(mqtt_client, payload)
    elif action == "LOCK":
        lock_slot()
        publish_status(mqtt_client, "locked")
        publish_ack(mqtt_client, payload, "locked", "Boitier verrouille.")
        publish_telemetry_now(mqtt_client)
    elif action == "UNLOCK":
        unlock_slot()
        publish_status(mqtt_client, "unlocked")
        publish_ack(mqtt_client, payload, "unlocked", "Boitier deverrouille.")
        publish_telemetry_now(mqtt_client)
    else:
        publish_ack(mqtt_client, payload, "error", "Commande inconnue.")


def connect_mqtt():
    """Connect MQTT and subscribe to the command topic."""
    client = MQTTClient(
        CLIENT_ID,
        MQTT_HOST,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=MQTT_KEEPALIVE_SECONDS,
    )
    client.set_callback(handle_command)
    client.connect()
    client.subscribe(TOPIC_CMD)
    print("MQTT connected to {}:{}.".format(MQTT_HOST, MQTT_PORT))
    print("Listening:", TOPIC_CMD)
    print("Telemetry:", TOPIC_TELEMETRY)
    return client


def update_energy(power_watts):
    """Integrate power into kWh when voltage is available."""
    global energy_kwh, last_power_at

    now = now_seconds()
    if last_power_at:
        elapsed = max(0, now - last_power_at)
        if state == "charging" and power_watts is not None:
            energy_kwh += (float(power_watts) * elapsed) / 3600000
    last_power_at = now


def safety_check(client, power_sample, environment):
    """Stop locally on wired safety conditions."""
    if state != "charging":
        return

    current = power_sample.get("current")
    temperature = environment.get("temperature")

    if PHYSICAL_INPUTS_ENABLED and not read_door_closed():
        publish_alert(client, "intrusion", "Boitier ouvert pendant la charge.")
        accept_stop(client, {"action": "STOP", "command_id": "local-intrusion"}, "intrusion")
    elif PHYSICAL_INPUTS_ENABLED and not read_cable_present():
        publish_alert(client, "cable_removed", "Câble retiré pendant la charge.")
        accept_stop(client, {"action": "STOP", "command_id": "local-cable"}, "cable_removed")
    elif current is not None and current > MAX_CURRENT_A:
        publish_alert(client, "overcurrent", "Courant trop eleve.")
        accept_stop(client, {"action": "STOP", "command_id": "local-overcurrent"}, "overcurrent")
    elif temperature is not None and temperature > MAX_TEMPERATURE_C:
        publish_alert(client, "overheat", "Temperature trop elevee.")
        accept_stop(client, {"action": "STOP", "command_id": "local-overheat"}, "overheat")


def publish_telemetry(client):
    """Publish one telemetry payload compatible with backend/Grafana."""
    environment = read_environment()
    power_sample = read_power_sample()
    update_energy(power_sample.get("power"))
    safety_check(client, power_sample, environment)

    payload = {
        "session_id": session_id,
        "state": state,
        "current": round_value(power_sample.get("current")),
        "voltage": round_value(power_sample.get("voltage"), 2),
        "power": round_value(power_sample.get("power"), 2),
        "energy_kwh": round_value(energy_kwh, 6),
        "temperature": round_value(environment.get("temperature"), 2),
        "humidity": round_value(environment.get("humidity"), 2),
        "heat_index": round_value(environment.get("heat_index"), 2),
        "door": reported_door_closed(),
        "cable": reported_cable_present(),
        "uptime_seconds": now_seconds(),
    }
    payload.update(device_identity())
    publish_json(client, TOPIC_TELEMETRY, payload)


def publish_telemetry_now(client):
    """Publish telemetry immediately and reset the periodic timer."""
    global last_telemetry_at
    publish_telemetry(client)
    last_telemetry_at = now_seconds()


def current_telemetry_interval():
    """Return the telemetry interval adapted to the current operating state."""
    if state in ("charging", "waiting_plug", "stopping", "error"):
        return TELEMETRY_ACTIVE_INTERVAL_SECONDS
    return TELEMETRY_IDLE_INTERVAL_SECONDS


def setup_hardware():
    """Initialize the sensors and optional physical I/O."""
    global dht_sensor, current_adc, ina219_i2c
    init_outputs()
    init_physical_inputs()
    dht_sensor = init_dht22()
    current_adc, ina219_i2c = init_current_sensor()
    stop_charge_output()
    lock_slot()


def main():
    """Main firmware loop."""
    global wlan, mqtt_client, last_telemetry_at, last_status_at

    setup_hardware()
    wlan = connect_wifi()
    mqtt_client = connect_mqtt()
    publish_status(mqtt_client, "boot")

    while True:
        try:
            mqtt_client.check_msg()
            now = now_seconds()

            if now - last_telemetry_at >= current_telemetry_interval():
                publish_telemetry_now(mqtt_client)

            if now - last_status_at >= STATUS_INTERVAL_SECONDS:
                publish_status(mqtt_client, "heartbeat")
                last_status_at = now

            time.sleep(0.2)
        except Exception as exc:
            print("Main loop error:", exc)
            time.sleep(2)
            try:
                if wlan is None or not wlan.isconnected():
                    wlan = connect_wifi()
                mqtt_client = connect_mqtt()
                publish_status(mqtt_client, "reconnected")
            except Exception as reconnect_exc:
                print("MQTT reconnect failed:", reconnect_exc)


main()
