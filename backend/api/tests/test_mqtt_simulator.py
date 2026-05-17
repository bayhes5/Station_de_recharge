from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone as django_timezone

from api.models import Device, Reservation, Session
from api.services.mqtt_simulator import build_telemetry_payload, telemetry_topic


def test_telemetry_topic_uses_project_topic_shape():
    """Build the same topic shape as ESP32 firmware telemetry."""
    assert telemetry_topic("station", "slot1") == "station/slot1/telemetry"
    assert (
        telemetry_topic("station", "slot1", "station-centre/borne-1")
        == "station/station-centre/borne-1/slot1/telemetry"
    )
    assert (
        telemetry_topic("station", "slot1", "station/station-centre/borne-1")
        == "station/station-centre/borne-1/slot1/telemetry"
    )


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


@pytest.mark.django_db
def test_simulator_can_target_latest_active_session(user, emplacements):
    """Publish dry-run telemetry only for the slot assigned to the active session."""
    borne = emplacements[1].borne
    borne.mqtt_prefix = "station-centre/borne-1"
    borne.save(update_fields=["mqtt_prefix"])
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[1],
        reference_code="QR-SIM-1",
        auth_choice="qr",
        date_debut=django_timezone.now() - timedelta(minutes=5),
        date_fin=django_timezone.now() + timedelta(minutes=30),
        statut="active",
    )
    session = Session.objects.create(
        reservation=reservation,
        emplacement=emplacements[1],
        start_time=django_timezone.now(),
    )
    Device.objects.create(
        emplacement=emplacements[1],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot2",
        status="online",
    )

    stdout = StringIO()
    call_command(
        "simulate_mqtt_telemetry",
        "--active-session",
        "--count",
        "1",
        "--dry-run",
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "station/station-centre/borne-1/slot2/telemetry" in output
    assert str(session.id_session) in output
    assert "station/slot1/telemetry" not in output
