from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any


SCENARIOS = ("normal", "intrusion", "cable_removed", "overheat", "overcurrent", "fault", "mixed")


def telemetry_topic(base_topic: str, slot_id: str) -> str:
    """Return the telemetry topic used by one simulated ESP32 slot."""
    return f"{base_topic}/{slot_id}/telemetry"


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
    current = _wave(base=1.2, amplitude=0.28, tick=tick, period=12)
    voltage = _wave(base=41.5, amplitude=0.8, tick=tick, period=18)
    temperature = _wave(base=31.0, amplitude=2.4, tick=tick, period=20)
    humidity = _wave(base=45.0, amplitude=4.0, tick=tick, period=25)
    door = True
    cable = True
    state = "charging"

    if scenario == "intrusion":
        door = False
    elif scenario == "cable_removed":
        cable = False
    elif scenario == "overheat":
        temperature = 64.0
    elif scenario == "overcurrent":
        current = 3.4
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
        return "overcurrent"
    return "normal"


def _wave(base: float, amplitude: float, tick: int, period: int) -> float:
    """Return a small deterministic sensor variation."""
    return base + amplitude * math.sin((tick % period) / period * math.tau)
