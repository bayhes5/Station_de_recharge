"""MicroPython firmware for one ESP32 charging slot.

This version is adapted for the current hardware test:
- DHT22 on GPIO15 for temperature and humidity.
- DFRobot SEN0214 analog 20A current sensor on GPIO34.
- Active-low lock relay on GPIO26.
- ESP32 identity fields: firmware version, IP address and MAC address.
- Door, cable and charge relay are optional and disabled by default until wired.

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

WIFI_SSID = "MetropoleVerte-IoT"
WIFI_PASSWORD = "NouveauMotDePasse8car"

# For the target station setup, use the Wi-Fi/AP IP of the Raspberry running
# Mosquitto. In the soutenance topology, ESP32 devices join the Raspberry
# access point on 192.168.20.0/24, so they reach Mosquitto through wlan0.
MQTT_HOST = "192.168.20.1"
MQTT_PORT = 1883
MQTT_USER = "esp32_station_demo_borne_1_slot1"
MQTT_PASSWORD = "TEST"
MQTT_KEEPALIVE_SECONDS = 60
MQTT_BASE_TOPIC = "station"
MQTT_TLS_ENABLED = False
MQTT_TLS_CA_CERT_FILE = "certs/metropole-verte-root-ca.der"
MQTT_TLS_SERVER_HOSTNAME = ""  # Use MQTT_HOST when empty.

# Must match the borne mqtt_prefix in the backend demo data.
# For the current demo this gives:
# station/station-demo/borne-1/slot1/telemetry
MQTT_TOPIC_PREFIX = "station-demo/borne-1"
SLOT_ID = "slot1"
CLIENT_ID = "esp32-station-demo-borne-1-slot1"
FIRMWARE_VERSION = "1.3.0-access-before-charge"
FIRMWARE_VERSION_FILE = "version.txt"

# DHT22, ESP32 identity, SEN0214 current and the lock relay are wired/reported
# for now. Door, cable and charge relay remain optional until wired.
PHYSICAL_INPUTS_ENABLED = False
LOCK_OUTPUT_ENABLED = True
CHARGE_RELAY_OUTPUT_ENABLED = False
SIMULATE_MISSING_SENSORS = False
SIMULATE_CABLE_PRESENT_FOR_AUTO_START = False

# DHT22 prototype wiring from TEMPERATUREHUMIDY.txt.
DHT_PIN = 15

# SEN0214 is a 5V analog 20A current sensor.
# Its output voltage is centered around VCC/2 and changes by about 100mV/A.
# IMPORTANT: protect the ESP32 ADC pin if the SEN0214 is powered at 5V.
CURRENT_SENSOR_MODE = "sen0214"  # "none", "sen0214", "adc" or "ina219".
ADC_CURRENT_PIN = 34
ADC_VREF = 3.3
ADC_RESOLUTION = 4095
ADC_CURRENT_INPUT_SCALE = 1.515
ADC_CURRENT_ZERO_VOLTAGE = 0.0
ADC_CURRENT_SENSITIVITY_V_PER_A = 0.100
SEN0214_ZERO_CURRENT_VOLTAGE = 2.5
SEN0214_SENSITIVITY_V_PER_A = 0.100
SEN0214_AUTO_CALIBRATE_ZERO = True
SEN0214_CALIBRATION_ROUNDS = 20
SEN0214_CALIBRATION_SAMPLES = 80
SEN0214_ABSOLUTE_CURRENT = True
ADC_AVERAGE_SAMPLES = 120
ADC_AVERAGE_DELAY_US = 500
ADC_NOISE_FLOOR_A = 0.05

# Prototype bus voltage. "fixed" publishes this configured value so Grafana can
# estimate power/energy. Use "adc" or "ina219" when a real voltage sensor is
# wired.
VOLTAGE_SENSOR_MODE = "fixed"  # "none", "fixed", "adc" or "ina219".
FIXED_BUS_VOLTAGE = 12.0
ADC_VOLTAGE_PIN = 35
ADC_VOLTAGE_SCALE = 1.0
ADC_VOLTAGE_OFFSET = 0.0
ADC_VOLTAGE_NOISE_FLOOR_V = 0.02

# Optional future INA219 wiring.
INA219_SDA_PIN = 21
INA219_SCL_PIN = 22
INA219_ADDRESS = 0x40
INA219_SHUNT_OHMS = 0.1

# Optional future physical wiring.
HALL_PIN = 19
DOOR_PIN = 25
LOCK_PIN = 26
LOCK_RELAY_ACTIVE_LOW = True
LOCK_AUTO_RELOCK_SECONDS = 30
CHARGE_RELAY_PIN = 22

# Optional local visual/acoustic indicators from the prototype alert circuit.
# GPIO18 follows the physical wiring chosen on the prototype board.
# The future MC-38 door contact is therefore moved to GPIO25.
LOCAL_ALERT_OUTPUTS_ENABLED = True
GREEN_LED_PIN = 2
YELLOW_LED_PIN = 4
RED_LED_PIN = 5
BUZZER_PIN = 18
LOCAL_ALARM_PIN = 27

TELEMETRY_ACTIVE_INTERVAL_SECONDS = 5
TELEMETRY_IDLE_INTERVAL_SECONDS = 30
STATUS_INTERVAL_SECONDS = 15
GREEN_CHARGING_BLINK_MS = 500
# Demo thresholds requested for the soutenance prototype.
# WARNING_CURRENT_A drives the yellow LED.
# MAX_CURRENT_A is the local safety threshold: red LED, buzzer, MQTT alert
# and automatic STOP when the current reaches the critical demo limit.
WARNING_CURRENT_A = 5.0
MAX_CURRENT_A = 6.0
WARNING_TEMPERATURE_C = 28.0
MAX_TEMPERATURE_C = 999.0


state = "idle"
session_id = ""
last_telemetry_at = 0
last_status_at = 0
last_power_at = 0
energy_kwh = 0.0

dht_sensor = None
current_adc = None
voltage_adc = None
ina219_i2c = None
current_zero_voltage = None
hall = None
door = None
lock = None
charge_relay = None
green_led = None
yellow_led = None
red_led = None
buzzer = None
local_alarm = None
lock_state_locked = None
unlock_deadline_at = 0
mqtt_client = None
wlan = None
reported_firmware_version = FIRMWARE_VERSION
last_local_alert_level = ""
green_blink_on = False
last_green_blink_ms = 0


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


def now_millis():
    """Return a monotonic millisecond clock for non-blocking LED blinking."""
    try:
        return time.ticks_ms()
    except AttributeError:
        return int(time.time() * 1000)


def elapsed_millis(current_ms, previous_ms):
    """Return elapsed milliseconds with MicroPython tick wrap-around support."""
    try:
        return time.ticks_diff(current_ms, previous_ms)
    except AttributeError:
        return current_ms - previous_ms


def round_value(value, digits=3):
    """Round numeric telemetry while keeping None values readable."""
    if value is None:
        return None
    return round(float(value), digits)


def format_mac(mac_bytes):
    """Return a colon-separated MAC address from MicroPython bytes."""
    return ":".join("{:02X}".format(value) for value in mac_bytes)


def load_firmware_version():
    """Return the version embedded in the firmware or stored on LittleFS."""
    try:
        with open(FIRMWARE_VERSION_FILE, "r") as version_file:
            version = version_file.read().strip()
        if version:
            print("Firmware version loaded from {}: {}".format(FIRMWARE_VERSION_FILE, version))
            return version
    except OSError:
        # Missing version file is expected on freshly flashed boards.
        pass
    except Exception as exc:
        print("Firmware version file read failed:", exc)
    return FIRMWARE_VERSION


def connect_wifi():
    """Connect to Wi-Fi and print the network identity."""
    station = network.WLAN(network.STA_IF)
    station.active(True)

    current_ssid = ""
    try:
        current_ssid = station.config("essid")
    except Exception:
        current_ssid = ""

    if station.isconnected() and current_ssid == WIFI_SSID:
        print("WiFi already connected to configured SSID:", WIFI_SSID)
    else:
        if station.isconnected():
            print("Disconnecting from previous WiFi:", current_ssid or "<unknown>")
            station.disconnect()
            time.sleep(1)

        # A soft reboot can keep stale Wi-Fi state on some MicroPython builds.
        # Restarting STA mode makes sure the new credentials are really used.
        station.active(False)
        time.sleep(1)
        station.active(True)

        print("Connecting to WiFi SSID:", WIFI_SSID)
        station.connect(WIFI_SSID, WIFI_PASSWORD)
        max_wait = 25
        while max_wait > 0 and not station.isconnected():
            max_wait -= 1
            time.sleep(1)

    if not station.isconnected():
        raise RuntimeError("WiFi connection failed")

    ip_address, netmask, gateway, dns = station.ifconfig()
    print("WiFi connected.")
    print("ESP32 IP:", ip_address)
    print("Netmask:", netmask)
    print("Gateway:", gateway)
    print("DNS:", dns)
    print("MQTT broker:", "{}:{}".format(MQTT_HOST, MQTT_PORT))
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
        "firmware_version": reported_firmware_version,
        "hardware_mac": hardware_mac,
        "ip_address": ip_address,
    }


def init_outputs():
    """Initialize optional relay outputs only when they are wired."""
    global lock, charge_relay
    if LOCK_OUTPUT_ENABLED:
        lock = Pin(LOCK_PIN, Pin.OUT)
        lock_slot()
        print("Lock relay ready on GPIO{}.".format(LOCK_PIN))
    else:
        print("Lock relay disabled.")

    if CHARGE_RELAY_OUTPUT_ENABLED:
        charge_relay = Pin(CHARGE_RELAY_PIN, Pin.OUT)
        charge_relay.value(0)
        print("Charge relay ready on GPIO{}.".format(CHARGE_RELAY_PIN))
    else:
        print("Charge relay disabled.")


def init_local_alert_outputs():
    """Initialize optional LED and buzzer outputs used by the prototype."""
    global green_led, yellow_led, red_led, buzzer, local_alarm
    if not LOCAL_ALERT_OUTPUTS_ENABLED:
        print("Local alert outputs disabled.")
        return

    green_led = Pin(GREEN_LED_PIN, Pin.OUT)
    yellow_led = Pin(YELLOW_LED_PIN, Pin.OUT)
    red_led = Pin(RED_LED_PIN, Pin.OUT)
    buzzer = Pin(BUZZER_PIN, Pin.OUT)
    local_alarm = Pin(LOCAL_ALARM_PIN, Pin.OUT)
    set_local_alert_outputs("idle")
    print(
        "Local alert outputs ready: green GPIO{}, yellow GPIO{}, red GPIO{}, buzzer GPIO{}, alarm GPIO{}.".format(
            GREEN_LED_PIN,
            YELLOW_LED_PIN,
            RED_LED_PIN,
            BUZZER_PIN,
            LOCAL_ALARM_PIN,
        )
    )


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


def read_average_adc(adc, samples=ADC_AVERAGE_SAMPLES, delay_us=ADC_AVERAGE_DELAY_US):
    """Return an averaged ADC value to reduce sensor noise."""
    total = 0
    for _ in range(samples):
        total += adc.read()
        if delay_us:
            time.sleep_us(delay_us)
    return total / samples


def adc_raw_to_sensor_voltage(raw):
    """Convert ESP32 ADC reading to the sensor output voltage."""
    gpio_voltage = (raw / ADC_RESOLUTION) * ADC_VREF
    return gpio_voltage * ADC_CURRENT_INPUT_SCALE


def calibrate_current_zero(adc):
    """Measure the no-load sensor voltage used as the zero-current reference."""
    print("Calibrating zero current. Make sure no load is connected.")
    time.sleep(2)

    total = 0.0
    for _ in range(SEN0214_CALIBRATION_ROUNDS):
        raw = read_average_adc(adc, samples=SEN0214_CALIBRATION_SAMPLES)
        total += adc_raw_to_sensor_voltage(raw)
        time.sleep(0.1)

    zero_voltage = total / SEN0214_CALIBRATION_ROUNDS
    print("Zero current voltage = {:.3f} V".format(zero_voltage))
    return zero_voltage


def init_adc_voltage_sensor():
    """Initialize the analog voltage input used by the prototype."""
    try:
        adc = ADC(Pin(ADC_VOLTAGE_PIN))
        adc.atten(ADC.ATTN_11DB)
        try:
            adc.width(ADC.WIDTH_12BIT)
        except Exception as exc:
            print("ADC voltage width configuration skipped:", exc)
        print("Analog voltage input ready on GPIO{}".format(ADC_VOLTAGE_PIN))
        return adc
    except Exception as exc:
        print("ADC voltage init failed:", exc)
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
    global current_zero_voltage
    if CURRENT_SENSOR_MODE == "ina219":
        return None, init_ina219()
    if CURRENT_SENSOR_MODE in ("adc", "sen0214"):
        adc = init_adc_current_sensor()
        if adc and CURRENT_SENSOR_MODE == "sen0214":
            if SEN0214_AUTO_CALIBRATE_ZERO:
                current_zero_voltage = calibrate_current_zero(adc)
            else:
                current_zero_voltage = SEN0214_ZERO_CURRENT_VOLTAGE
        return adc, None
    print("Current sensor disabled.")
    return None, None


def init_voltage_sensor():
    """Initialize the configured voltage sensor backend."""
    if VOLTAGE_SENSOR_MODE == "adc":
        return init_adc_voltage_sensor()
    if VOLTAGE_SENSOR_MODE == "ina219":
        print("Voltage will be read through INA219.")
        return None
    if VOLTAGE_SENSOR_MODE == "fixed":
        print("Fixed prototype bus voltage: {:.2f}V.".format(FIXED_BUS_VOLTAGE))
        return None
    print("Voltage sensor disabled.")
    return None


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
    raw = read_average_adc(current_adc)
    adc_voltage = (raw / ADC_RESOLUTION) * ADC_VREF
    sensor_voltage = adc_raw_to_sensor_voltage(raw)

    if CURRENT_SENSOR_MODE == "sen0214":
        zero_voltage = current_zero_voltage
        if zero_voltage is None:
            zero_voltage = SEN0214_ZERO_CURRENT_VOLTAGE
        current = (
            sensor_voltage - zero_voltage
        ) / SEN0214_SENSITIVITY_V_PER_A
        if SEN0214_ABSOLUTE_CURRENT:
            current = abs(current)
    else:
        current = (
            sensor_voltage - ADC_CURRENT_ZERO_VOLTAGE
        ) / ADC_CURRENT_SENSITIVITY_V_PER_A

    if abs(current) < ADC_NOISE_FLOOR_A:
        current = 0.0
    if current < 0:
        current = 0.0
    print(
        "Current ADC raw={} adc={:.3f}V sensor={:.3f}V current={:.2f}A".format(
            raw,
            adc_voltage,
            sensor_voltage,
            current,
        )
    )
    return current


def read_adc_voltage():
    """Read voltage from a simple analog input and publish it as telemetry."""
    if voltage_adc is None:
        return None
    raw = voltage_adc.read()
    adc_voltage = (raw / ADC_RESOLUTION) * ADC_VREF
    measured_voltage = (adc_voltage * ADC_VOLTAGE_SCALE) + ADC_VOLTAGE_OFFSET
    if abs(measured_voltage) < ADC_VOLTAGE_NOISE_FLOOR_V:
        measured_voltage = 0.0
    print(
        "Voltage ADC raw={} adc={:.3f}V measured={:.2f}V".format(
            raw,
            adc_voltage,
            measured_voltage,
        )
    )
    return max(0.0, measured_voltage)


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
    current = None
    voltage = None
    power = None

    if CURRENT_SENSOR_MODE == "ina219":
        sample = read_ina219_power()
        if sample["current"] is not None:
            return sample

    if CURRENT_SENSOR_MODE in ("adc", "sen0214"):
        current = read_adc_current()
    if current is None and CURRENT_SENSOR_MODE != "none" and SIMULATE_MISSING_SENSORS:
        current = 1.2 if state == "charging" else 0.0

    if VOLTAGE_SENSOR_MODE == "adc":
        voltage = read_adc_voltage()
    elif VOLTAGE_SENSOR_MODE == "fixed":
        voltage = FIXED_BUS_VOLTAGE
    elif VOLTAGE_SENSOR_MODE == "ina219":
        sample = read_ina219_power()
        voltage = sample.get("voltage")
        if current is None:
            current = sample.get("current")

    if voltage is None and VOLTAGE_SENSOR_MODE != "none" and SIMULATE_MISSING_SENSORS:
        voltage = 12.0 if state == "charging" else 0.0

    if current is not None and voltage is not None:
        power = voltage * current

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
        if SIMULATE_CABLE_PRESENT_FOR_AUTO_START and state in (
            "waiting_plug",
            "charging",
            "stopping",
        ):
            return True
        return None
    return read_cable_present()


def reported_door_closed():
    """Return the door telemetry value, or None when the sensor is not wired."""
    if not PHYSICAL_INPUTS_ENABLED or door is None:
        return None
    return read_door_closed()


def reported_lock_locked():
    """Return the last commanded lock state, or None when the relay is disabled."""
    if lock is None:
        return None
    return lock_state_locked


def lock_pin_value(locked):
    """Return the relay GPIO value for a locked or unlocked state."""
    if locked:
        return 1 if LOCK_RELAY_ACTIVE_LOW else 0
    return 0 if LOCK_RELAY_ACTIVE_LOW else 1


def lock_slot():
    """De-energize the lock relay and return the lock to its rest position."""
    global lock_state_locked
    lock_state_locked = True
    if lock is not None:
        lock.value(lock_pin_value(True))


def unlock_slot():
    """Energize the lock relay to open the lock."""
    global lock_state_locked
    lock_state_locked = False
    if lock is not None:
        lock.value(lock_pin_value(False))


def clear_unlock_window():
    """Clear any pending auto-relock deadline."""
    global unlock_deadline_at
    unlock_deadline_at = 0


def open_unlock_window():
    """Open the lock and schedule a non-blocking auto-relock deadline."""
    global unlock_deadline_at
    unlock_slot()
    unlock_deadline_at = now_seconds() + LOCK_AUTO_RELOCK_SECONDS


def enforce_unlock_timeout(client):
    """Relock automatically when access was granted but no charge started."""
    global unlock_deadline_at, state, session_id
    if not unlock_deadline_at:
        return
    if state == "charging":
        clear_unlock_window()
        return
    if now_seconds() >= unlock_deadline_at:
        lock_slot()
        clear_unlock_window()
        state = "idle"
        set_local_alert_outputs("idle")
        publish_status(client, "locked", "auto_relock_no_charge")
        publish_telemetry_now(client)
        session_id = ""


def start_charge_output():
    """Enable the charge relay when it is wired."""
    if charge_relay is not None:
        charge_relay.value(1)


def stop_charge_output():
    """Disable the charge relay when it is wired."""
    if charge_relay is not None:
        charge_relay.value(0)


def set_output(pin, enabled):
    """Set one optional output pin when it is available."""
    if pin is not None:
        pin.value(1 if enabled else 0)


def compute_local_alert_level(power_sample, environment):
    """Return idle, normal, warning or danger for local LEDs and buzzer."""
    current = power_sample.get("current")
    temperature = environment.get("temperature")

    if current is not None and current >= MAX_CURRENT_A:
        return "danger"
    if temperature is not None and temperature > MAX_TEMPERATURE_C:
        return "danger"
    if current is not None and current >= WARNING_CURRENT_A:
        return "warning"
    if temperature is not None and temperature >= WARNING_TEMPERATURE_C:
        return "warning"
    if state in ("charging", "waiting_plug"):
        return "normal"
    return "idle"


def set_local_alert_outputs(level):
    """Apply the current local alert level to LEDs, buzzer and alarm pin."""
    set_output(green_led, level == "normal" and state != "charging")
    set_output(yellow_led, level == "warning")
    set_output(red_led, level == "danger")
    set_output(buzzer, level == "danger")
    set_output(local_alarm, level == "danger")


def refresh_green_charge_blink():
    """Blink the green LED while the charge is physically active."""
    global green_blink_on, last_green_blink_ms
    if green_led is None:
        return
    if state != "charging" or last_local_alert_level in ("warning", "danger"):
        green_blink_on = False
        last_green_blink_ms = 0
        return

    now = now_millis()
    if not last_green_blink_ms or elapsed_millis(now, last_green_blink_ms) >= GREEN_CHARGING_BLINK_MS:
        green_blink_on = not green_blink_on
        last_green_blink_ms = now
        set_output(green_led, green_blink_on)


def update_local_alert_outputs(power_sample, environment):
    """Refresh local indicators and publish one message when the level changes."""
    global last_local_alert_level
    level = compute_local_alert_level(power_sample, environment)
    set_local_alert_outputs(level)

    if level != last_local_alert_level:
        print("Local alert level:", level)
        last_local_alert_level = level
    refresh_green_charge_blink()


def publish_json(client, mqtt_topic, payload):
    """Publish one JSON message on MQTT."""
    client.publish(mqtt_topic, ujson.dumps(payload))


def mqtt_json_string(value):
    """Return a JSON string literal for compact manually ordered MQTT payloads."""
    return ujson.dumps("" if value is None else str(value))


def publish_status(client, event, reason=""):
    """Publish a status event consumed by the backend supervision bridge."""
    payload = {
        "event": event,
        "reason": reason,
        "state": state,
        "session_id": session_id,
        "door": reported_door_closed(),
        "cable": reported_cable_present(),
        "lock": reported_lock_locked(),
        "uptime_seconds": now_seconds(),
    }
    payload.update(device_identity())
    publish_json(client, TOPIC_STATUS, payload)


def publish_ack(client, command_payload, status, message=""):
    """Publish an ACK matching the Raspberry command_id/action contract."""
    command_id = str(command_payload.get("command_id") or "")
    action = str(command_payload.get("action") or "").upper()
    related_session = session_id or str(command_payload.get("session_id") or "")
    # Keep ACKs compact and ordered. MicroPython can truncate long MQTT JSON
    # payloads on constrained boards; the Raspberry needs these fields first.
    payload = (
        '{"command_id":'
        + mqtt_json_string(command_id)
        + ',"action":'
        + mqtt_json_string(action)
        + ',"status":'
        + mqtt_json_string(status)
        + ',"state":'
        + mqtt_json_string(state)
        + ',"session_id":'
        + mqtt_json_string(related_session)
        + ',"source":"esp32"}'
    )
    client.publish(TOPIC_ACK, payload)


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


def accept_unlock(client, payload):
    """Open the box after reservation authentication, before electrical charge."""
    global state, session_id

    if state == "charging":
        publish_ack(client, payload, "denied", "Charge déjà active.")
        return

    session_id = str(payload.get("session_id") or session_id or "")
    state = "waiting_plug"
    set_local_alert_outputs("normal")
    publish_ack(client, payload, "unlocked", "Boîtier déverrouillé.")
    open_unlock_window()
    publish_status(client, "unlocked")
    publish_telemetry_now(client)


def accept_start(client, payload):
    """Start electrical charging after the box has been opened and plugged."""
    global state, session_id

    if state == "charging" and session_id and payload.get("session_id") != session_id:
        publish_ack(client, payload, "denied", "Une charge est déjà active.")
        return

    session_id = str(payload.get("session_id") or session_id or "")
    if read_cable_present() and read_door_closed():
        start_charge_output()
        lock_slot()
        clear_unlock_window()
        state = "charging"
        set_local_alert_outputs("normal")
        publish_status(client, "charging_started")
        publish_ack(client, payload, "charging", "Charge démarrée.")
        publish_telemetry_now(client)
    else:
        stop_charge_output()
        state = "waiting_plug"
        set_local_alert_outputs("normal")
        publish_status(client, "waiting_plug")
        publish_ack(client, payload, "accepted", "En attente du câble et du boîtier fermé.")
        publish_telemetry_now(client)


def accept_stop(client, payload, reason="remote_stop"):
    """Accept STOP and move back to idle."""
    global state, session_id

    stop_charge_output()
    state = "idle"
    set_local_alert_outputs("idle")
    publish_ack(client, payload, "stopped", "Charge arrêtée.")
    open_unlock_window()
    publish_status(client, "stopped", reason)
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
        clear_unlock_window()
        publish_status(mqtt_client, "locked")
        publish_ack(mqtt_client, payload, "locked", "Boîtier verrouillé.")
        publish_telemetry_now(mqtt_client)
    elif action == "UNLOCK":
        accept_unlock(mqtt_client, payload)
    else:
        publish_ack(mqtt_client, payload, "error", "Commande inconnue.")


def connect_mqtt():
    """Connect MQTT and subscribe to the command topic."""
    kwargs = {}
    if MQTT_TLS_ENABLED:
        kwargs["ssl"] = True
        kwargs["ssl_params"] = build_mqtt_tls_params()

    try:
        client = MQTTClient(
            CLIENT_ID,
            MQTT_HOST,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=MQTT_KEEPALIVE_SECONDS,
            **kwargs
        )
    except TypeError:
        if MQTT_TLS_ENABLED:
            raise RuntimeError("MQTT TLS requires an umqtt.simple build with ssl_params support.")
        raise
    client.set_callback(handle_command)
    client.connect()
    client.subscribe(TOPIC_CMD)
    print("MQTT connected to {}:{}.".format(MQTT_HOST, MQTT_PORT))
    print("Listening:", TOPIC_CMD)
    print("Telemetry:", TOPIC_TELEMETRY)
    return client


def build_mqtt_tls_params():
    """Build TLS parameters for MQTT using the CA certificate stored on LittleFS."""
    try:
        import ssl
    except ImportError:
        raise RuntimeError("MQTT TLS requires the MicroPython ssl module.")

    try:
        with open(MQTT_TLS_CA_CERT_FILE, "rb") as ca_file:
            ca_data = ca_file.read()
    except OSError:
        raise RuntimeError("MQTT TLS CA certificate not found: {}".format(MQTT_TLS_CA_CERT_FILE))

    server_hostname = MQTT_TLS_SERVER_HOSTNAME or MQTT_HOST
    return {
        "cert_reqs": getattr(ssl, "CERT_REQUIRED", 2),
        "cadata": ca_data,
        "server_hostname": server_hostname,
    }


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
    elif current is not None and current >= MAX_CURRENT_A:
        publish_alert(client, "overcurrent", "Courant trop élevé.")
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
    update_local_alert_outputs(power_sample, environment)

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
        "local_alert_level": last_local_alert_level,
        "door": reported_door_closed(),
        "cable": reported_cable_present(),
        "lock": reported_lock_locked(),
        "uptime_seconds": now_seconds(),
    }
    payload.update(device_identity())
    print("Telemetry payload:", ujson.dumps(payload))
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
    global dht_sensor, current_adc, voltage_adc, ina219_i2c
    init_outputs()
    init_local_alert_outputs()
    init_physical_inputs()
    dht_sensor = init_dht22()
    current_adc, ina219_i2c = init_current_sensor()
    voltage_adc = init_voltage_sensor()
    stop_charge_output()
    lock_slot()


def main():
    """Main firmware loop."""
    global wlan, mqtt_client, last_telemetry_at, last_status_at, reported_firmware_version

    setup_hardware()
    reported_firmware_version = load_firmware_version()
    wlan = connect_wifi()
    mqtt_client = connect_mqtt()
    publish_status(mqtt_client, "boot")

    while True:
        try:
            mqtt_client.check_msg()
            now = now_seconds()
            enforce_unlock_timeout(mqtt_client)
            refresh_green_charge_blink()

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
