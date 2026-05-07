from datetime import datetime, timezone

import pytest

from api.services.mqtt_simulator import build_telemetry_payload, telemetry_topic


def test_telemetry_topic_uses_project_topic_shape():
    """Build the same topic shape as ESP32 firmware telemetry."""
    assert telemetry_topic("station", "slot1") == "station/slot1/telemetry"


def test_build_telemetry_payload_contains_expected_sensor_fields():
    """Generate a realistic normal telemetry payload."""
    payload = build_telemetry_payload(
        "slot1",
        tick=1,
        started_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
    )

    assert payload["slot_id"] == "slot1"
    assert payload["state"] == "charging"
    assert payload["door"] is True
    assert payload["cable"] is True
    assert payload["current"] > 0
    assert payload["voltage"] > 0
    assert payload["power"] == pytest.approx(payload["current"] * payload["voltage"], abs=0.05)
    assert payload["timestamp"].endswith("Z")


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("intrusion", {"door": False}),
        ("cable_removed", {"cable": False}),
        ("overheat", {"temperature": 64.0}),
        ("overcurrent", {"current": 3.4}),
        ("fault", {"state": "error"}),
    ],
)
def test_build_telemetry_payload_can_emit_operational_scenarios(scenario, expected):
    """Generate each supervision scenario needed by the alerting pipeline."""
    payload = build_telemetry_payload("slot1", tick=1, scenario=scenario)

    for key, value in expected.items():
        assert payload[key] == value


def test_build_telemetry_payload_rejects_unknown_scenario():
    """Fail fast when a simulator scenario is misspelled."""
    with pytest.raises(ValueError):
        build_telemetry_payload("slot1", tick=1, scenario="unknown")
