import importlib
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture()
def mqtt_contract(monkeypatch):
    monkeypatch.syspath_prepend(str(APP_DIR))
    sys.modules.pop("mqtt_contract", None)
    return importlib.import_module("mqtt_contract")


def test_start_and_stop_commands_require_session_id(mqtt_contract):
    payload = {
        "command_id": "cmd-start-1",
        "action": "START",
        "issued_at": "2026-05-17T14:00:00+00:00",
    }

    assert mqtt_contract.validate_command_payload(payload) == [
        "session_id is required for START and STOP commands."
    ]

    payload["session_id"] = "session-1"
    assert mqtt_contract.validate_command_payload(payload) == []


def test_lock_command_does_not_require_session_id(mqtt_contract):
    payload = {
        "command_id": "cmd-lock-1",
        "action": "LOCK",
        "issued_at": "2026-05-17T14:00:00+00:00",
    }

    assert mqtt_contract.validate_command_payload(payload) == []


def test_ack_contract_rejects_wrong_command_id_or_unknown_status(mqtt_contract):
    payload = {
        "command_id": "cmd-other",
        "action": "START",
        "status": "stopped",
    }

    errors = mqtt_contract.validate_ack_payload(
        payload,
        expected_action="START",
        expected_command_id="cmd-start-1",
    )

    assert "ack command_id does not match the command_id." in errors
    assert "unknown ACK status for START: stopped." in errors
    assert mqtt_contract.ack_confirms_command(payload, "START") is False


def test_waiting_cable_status_is_accepted_as_legacy_alias(mqtt_contract):
    payload = {
        "state": "waiting_cable",
        "session_id": "session-1",
    }

    assert mqtt_contract.normalize_state("waiting_cable") == "waiting_plug"
    assert mqtt_contract.validate_status_payload(payload) == []


@pytest.mark.parametrize(
    ("payload", "expected_alert"),
    [
        ({"state": "charging", "cable": False}, "cable_removed"),
        ({"state": "charging", "door": False, "cable": True}, "intrusion"),
        (
            {"state": "charging", "door": True, "cable": True, "intrusion": True},
            "intrusion",
        ),
        ({"state": "charging", "door": True, "cable": True, "lock": False}, "lock_unlocked"),
        ({"state": "charging", "temperature": 60}, "overheat"),
        ({"state": "charging", "current": 3.0}, "overcurrent"),
        ({"state": "error"}, "state_error"),
    ],
)
def test_detect_safety_alert_matches_operational_policy(mqtt_contract, payload, expected_alert):
    assert mqtt_contract.detect_safety_alert(payload) == expected_alert


def test_telemetry_requires_slot_and_session_while_charging(mqtt_contract):
    errors = mqtt_contract.validate_telemetry_payload({"state": "charging"})

    assert "slot_id is required." in errors
    assert "session_id is required while charging." in errors

    assert mqtt_contract.validate_telemetry_payload(
        {
            "slot_id": "slot1",
            "session_id": "session-1",
            "state": "charging",
            "temperature": 31.5,
            "humidity": 44.0,
        }
    ) == []
