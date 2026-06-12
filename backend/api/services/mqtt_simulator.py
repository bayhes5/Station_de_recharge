from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any


SCENARIOS = (
    "normal",
    "intrusion",
    "cable_removed",
    "lock_unlocked",
    "overheat",
    "overcurrent",
    "fault",
    "mixed",
)


def telemetry_topic(base_topic: str, slot_id: str, topic_prefix: str = "") -> str:
    """Return the telemetry topic used by one simulated ESP32 slot."""
    normalized_base = str(base_topic or "station").strip("/")
    normalized_prefix = str(topic_prefix or "").strip("/")
    if normalized_prefix:
        if normalized_prefix == normalized_base or normalized_prefix.startswith(f"{normalized_base}/"):
            return f"{normalized_prefix}/{slot_id}/telemetry"
        return f"{normalized_base}/{normalized_prefix}/{slot_id}/telemetry"
    return f"{normalized_base}/{slot_id}/telemetry"


def build_telemetry_payload(
    slot_id: str,
    tick: int,
    scenario: str = "normal",
    session_id: str = "simulation",
    started_at: datetime | None = None,
) -> dict[str, Any]:
    """Build one realistic MQTT telemetry payload for local supervision tests."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Scenario inconnu: {scenario}")

    scenario = _scenario_for_tick(scenario, tick)
    timestamp = (started_at or datetime.now(timezone.utc)) + timedelta(seconds=tick)
    current = _smooth_current(tick)
    voltage = _smooth_voltage(tick)
    temperature = _smooth_temperature(tick)
    humidity = _smooth_humidity(tick)
    door = True
    cable = True
    lock = True
    intrusion = False
    state = "charging"

    if scenario == "intrusion":
        door = False
        intrusion = True
    elif scenario == "cable_removed":
        cable = False
    elif scenario == "lock_unlocked":
        lock = False
    elif scenario == "overheat":
        temperature = 64.0
    elif scenario == "overcurrent":
        current = 4.4
    elif scenario == "fault":
        state = "error"

    power = current * voltage
    energy_kwh = max(tick, 1) * power / 3600 / 1000
    return {
        "slot_id": slot_id,
        "session_id": session_id,
        "state": state,
        "current": round(current, 3),
        "voltage": round(voltage, 2),
        "power": round(power, 2),
        "energy_kwh": round(energy_kwh, 6),
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 2),
        "door": door,
        "cable": cable,
        "lock": lock,
        "intrusion": intrusion,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
    }


def _scenario_for_tick(scenario: str, tick: int) -> str:
    """Resolve the active scenario for one tick."""
    if scenario != "mixed":
        return scenario
    cycle = tick % 40
    if 10 <= cycle < 14:
        return "intrusion"
    if 20 <= cycle < 24:
        return "overheat"
    if 30 <= cycle < 34:
        return "lock_unlocked"
    if 34 <= cycle < 37:
        return "overcurrent"
    return "normal"


def _smooth_current(tick: int) -> float:
    """Return a stable prototype charging current in amperes."""
    warmup = min(max(tick, 0) / 90, 1)
    base = 1.05 + 0.12 * warmup
    slow_ripple = 0.025 * math.sin((tick % 180) / 180 * math.tau)
    sensor_noise = 0.008 * math.sin((tick % 23) / 23 * math.tau)
    return max(0.0, base + slow_ripple + sensor_noise)


def _smooth_voltage(tick: int) -> float:
    """Return the fixed 12 V prototype bus voltage with tiny ADC variation."""
    return 12.0 + 0.025 * math.sin((tick % 240) / 240 * math.tau)


def _smooth_temperature(tick: int) -> float:
    """Return a slow DHT22 temperature drift during a charge."""
    thermal_rise = 1.8 * (1 - math.exp(-max(tick, 0) / 900))
    ambient_ripple = 0.12 * math.sin((tick % 360) / 360 * math.tau)
    return 24.6 + thermal_rise + ambient_ripple


def _smooth_humidity(tick: int) -> float:
    """Return a mostly stable DHT22 humidity value."""
    slow_drop = 0.6 * (1 - math.exp(-max(tick, 0) / 1200))
    ambient_ripple = 0.18 * math.sin((tick % 420) / 420 * math.tau)
    return 48.0 - slow_drop + ambient_ripple
