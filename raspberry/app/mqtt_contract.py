"""Executable MQTT contract shared by Raspberry tests and client code."""

from __future__ import annotations

from typing import Any


COMMAND_ACTIONS = {"START", "STOP", "LOCK", "UNLOCK"}
SESSION_COMMAND_ACTIONS = {"START", "STOP"}

CONFIRMED_ACK_STATUSES = {
    "START": {"accepted", "reserved", "ready", "charging", "charging_started"},
    "STOP": {"accepted", "stopped", "idle"},
    "LOCK": {"accepted", "locked"},
    "UNLOCK": {"accepted", "unlocked"},
}
REJECTED_ACK_STATUSES = {"denied", "error", "failed", "fault", "rejected"}

IDLE = "idle"
RESERVED = "reserved"
ACCESS_VALIDATED = "access_validated"
WAITING_PLUG = "waiting_plug"
CHARGING = "charging"
CHARGING_STARTED = "charging_started"
STOPPING = "stopping"
STOPPED = "stopped"
ERROR = "error"
FAULT = "fault"

LEGACY_STATE_ALIASES = {
    "waiting_cable": WAITING_PLUG,
}
KNOWN_STATES = {
    IDLE,
    RESERVED,
    ACCESS_VALIDATED,
    WAITING_PLUG,
    CHARGING,
    CHARGING_STARTED,
    STOPPING,
    STOPPED,
    ERROR,
    FAULT,
}
ACTIVE_CHARGE_STATES = {CHARGING, CHARGING_STARTED}

OVERHEAT_TEMPERATURE_C = 60.0
OVERCURRENT_A = 3.0
SAFETY_ALERT_TYPES = {
    "cable_removed",
    "intrusion",
    "lock_unlocked",
    "overheat",
    "overcurrent",
    "state_error",
}


def normalize_action(action: Any) -> str:
    """Return the canonical MQTT action name."""
    return str(action or "").strip().upper()


def normalize_status(status: Any) -> str:
    """Return the canonical lower-case MQTT status value."""
    return str(status or "").strip().lower()


def normalize_state(state: Any) -> str:
    """Return the canonical lower-case MQTT state value."""
    normalized = normalize_status(state)
    return LEGACY_STATE_ALIASES.get(normalized, normalized)


def ack_status(ack_payload: dict[str, Any] | None) -> str:
    """Extract the normalized status from an ESP32 ACK payload."""
    if not ack_payload:
        return ""
    return normalize_status(ack_payload.get("status") or ack_payload.get("state"))


def ack_is_rejected(ack_payload: dict[str, Any] | None) -> bool:
    """Return whether an ACK explicitly rejects a command."""
    return ack_status(ack_payload) in REJECTED_ACK_STATUSES


def ack_confirms_command(ack_payload: dict[str, Any] | None, action: str) -> bool:
    """Return whether an ACK is an operational confirmation."""
    status = ack_status(ack_payload)
    if not status or status in REJECTED_ACK_STATUSES:
        return False
    return status in CONFIRMED_ACK_STATUSES.get(normalize_action(action), {"accepted"})


def validate_command_payload(payload: dict[str, Any]) -> list[str]:
    """Validate a Raspberry -> ESP32 command payload."""
    errors = _ensure_object(payload)
    if errors:
        return errors

    _require_fields(payload, ("command_id", "action", "issued_at"), errors)
    action = normalize_action(payload.get("action"))
    if action and action not in COMMAND_ACTIONS:
        errors.append(f"action must be one of {', '.join(sorted(COMMAND_ACTIONS))}.")
    if action in SESSION_COMMAND_ACTIONS and not str(payload.get("session_id") or "").strip():
        errors.append("session_id is required for START and STOP commands.")
    return errors


def validate_ack_payload(
    payload: dict[str, Any],
    *,
    expected_action: str = "",
    expected_command_id: str = "",
) -> list[str]:
    """Validate an ESP32 -> Raspberry ACK payload."""
    errors = _ensure_object(payload)
    if errors:
        return errors

    _require_fields(payload, ("command_id", "action", "status"), errors)
    action = normalize_action(payload.get("action"))
    expected_action = normalize_action(expected_action)
    if action and action not in COMMAND_ACTIONS:
        errors.append(f"action must be one of {', '.join(sorted(COMMAND_ACTIONS))}.")
    if expected_action and action and action != expected_action:
        errors.append("ack action does not match the command action.")

    command_id = str(payload.get("command_id") or "").strip()
    expected_command_id = str(expected_command_id or "").strip()
    if expected_command_id and command_id and command_id != expected_command_id:
        errors.append("ack command_id does not match the command_id.")

    status = ack_status(payload)
    known_statuses = REJECTED_ACK_STATUSES | CONFIRMED_ACK_STATUSES.get(action, set())
    if status and status not in known_statuses:
        errors.append(f"unknown ACK status for {action or 'command'}: {status}.")
    return errors


def validate_status_payload(payload: dict[str, Any]) -> list[str]:
    """Validate an ESP32 status or heartbeat payload."""
    errors = _ensure_object(payload)
    if errors:
        return errors

    _require_fields(payload, ("state",), errors)
    state = normalize_state(payload.get("state") or payload.get("status") or payload.get("event"))
    if state and state not in KNOWN_STATES:
        errors.append(f"unknown ESP32 state: {state}.")
    if state in ACTIVE_CHARGE_STATES and not str(payload.get("session_id") or "").strip():
        errors.append("session_id is required while charging.")
    return errors


def validate_telemetry_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the minimum telemetry contract accepted from an ESP32."""
    errors = _ensure_object(payload)
    if errors:
        return errors

    _require_fields(payload, ("slot_id", "state"), errors)
    state = normalize_state(payload.get("state"))
    if state and state not in KNOWN_STATES:
        errors.append(f"unknown ESP32 state: {state}.")
    if state in ACTIVE_CHARGE_STATES and not str(payload.get("session_id") or "").strip():
        errors.append("session_id is required while charging.")
    return errors


def detect_safety_alert(payload: dict[str, Any]) -> str:
    """Return the expected alert type for one critical telemetry payload."""
    if not isinstance(payload, dict):
        return ""

    state = normalize_state(payload.get("state") or payload.get("status") or payload.get("event"))
    if state in {ERROR, FAULT}:
        return "state_error"
    if state in ACTIVE_CHARGE_STATES and _is_false(payload.get("cable")):
        return "cable_removed"
    if state in ACTIVE_CHARGE_STATES and (
        _is_false(payload.get("door")) or _is_true(payload.get("intrusion"))
    ):
        return "intrusion"
    if state in ACTIVE_CHARGE_STATES and _is_false(payload.get("lock")):
        return "lock_unlocked"

    temperature = _as_float(payload.get("temperature"))
    if temperature is not None and temperature >= OVERHEAT_TEMPERATURE_C:
        return "overheat"

    current = _as_float(payload.get("current"))
    if current is not None and current >= OVERCURRENT_A:
        return "overcurrent"
    return ""


def _ensure_object(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        return []
    return ["payload must be a JSON object."]


def _require_fields(payload: dict[str, Any], fields: tuple[str, ...], errors: list[str]) -> None:
    for field in fields:
        if payload.get(field) in (None, ""):
            errors.append(f"{field} is required.")


def _is_false(value: Any) -> bool:
    if value is False:
        return True
    return isinstance(value, str) and value.strip().lower() in {"false", "0", "no", "off"}


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in {"true", "1", "yes", "on"}


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
