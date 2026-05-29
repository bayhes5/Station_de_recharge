from __future__ import annotations

from django.utils import timezone

from api.models import ChargeSessionState, Session


START_WAITING_STATUSES = {"accepted", "reserved", "ready", "access_validated", "waiting_plug"}
START_CHARGING_STATUSES = {"charging", "charging_started"}
UNLOCK_WAITING_STATUSES = {"accepted", "unlocked", "waiting_plug"}
STOP_ACK_STATUSES = {"accepted", "stopped", "idle"}
ERROR_STATES = {"error", "fault", "emergency", "rejected", "failed"}
ACTIVE_SESSION_STATES = {
    ChargeSessionState.RESERVED,
    ChargeSessionState.ACCESS_VALIDATED,
    ChargeSessionState.WAITING_PLUG,
    ChargeSessionState.CHARGING,
    ChargeSessionState.STOPPING,
}
OPEN_SESSION_STATES = ACTIVE_SESSION_STATES | {ChargeSessionState.ERROR}


class ChargeSessionStateError(ValueError):
    """Raised when a backend charge session transition is not allowed."""


def session_is_open(session: Session) -> bool:
    """Return whether the session still represents a non-closed charge."""
    return session.end_time is None and session.charge_state in OPEN_SESSION_STATES


def ensure_session_can_be_started(session: Session) -> None:
    """Reject a new access/start attempt once the session is already engaged."""
    if session.end_time is not None or session.charge_state == ChargeSessionState.STOPPED:
        raise ChargeSessionStateError("Cette session de charge est déjà clôturée.")
    if session.charge_state in {
        ChargeSessionState.WAITING_PLUG,
        ChargeSessionState.CHARGING,
        ChargeSessionState.STOPPING,
    }:
        raise ChargeSessionStateError("Une session de charge est déjà engagée.")
    if session.charge_state == ChargeSessionState.ERROR:
        raise ChargeSessionStateError("Cette session est en erreur et nécessite une intervention.")


def set_session_state(
    session: Session,
    state: ChargeSessionState | str,
    *,
    now=None,
    save: bool = True,
) -> Session:
    """Persist a charge state change on a session."""
    normalized_state = ChargeSessionState(state)
    if session.charge_state == normalized_state and session.charge_state_updated_at:
        return session

    session.charge_state = normalized_state
    session.charge_state_updated_at = now or timezone.now()
    if save:
        session.save(update_fields=["charge_state", "charge_state_updated_at"])
    return session


def mark_access_validated(session: Session, *, now=None) -> Session:
    """Record that authentication succeeded and the box may be unlocked."""
    ensure_session_can_be_started(session)
    return set_session_state(session, ChargeSessionState.ACCESS_VALIDATED, now=now)


def mark_start_ack(session: Session | None, ack_status: str, *, now=None) -> Session | None:
    """Move a session after a START acknowledgement from the ESP32."""
    if session is None or not session_is_open(session):
        return session

    normalized = str(ack_status or "").strip().lower()
    if normalized in START_CHARGING_STATUSES:
        return set_session_state(session, ChargeSessionState.CHARGING, now=now)
    if normalized in START_WAITING_STATUSES:
        return set_session_state(session, ChargeSessionState.WAITING_PLUG, now=now)
    if normalized in ERROR_STATES:
        return set_session_state(session, ChargeSessionState.ERROR, now=now)
    return session


def mark_stop_requested(session: Session | None, *, now=None) -> Session | None:
    """Record that the backend or edge device is stopping an open session."""
    if session is None or not session_is_open(session):
        return session
    if session.charge_state != ChargeSessionState.STOPPED:
        return set_session_state(session, ChargeSessionState.STOPPING, now=now)
    return session


def mark_stopped(session: Session, *, now=None, save: bool = True) -> Session:
    """Record that a session is fully stopped from the backend point of view."""
    return set_session_state(session, ChargeSessionState.STOPPED, now=now, save=save)


def mark_error(session: Session | None, *, now=None) -> Session | None:
    """Record an abnormal state while keeping the session visible for operations."""
    if session is None or not session_is_open(session):
        return session
    return set_session_state(session, ChargeSessionState.ERROR, now=now)


def mark_state_from_device(session: Session | None, state: str, *, now=None) -> Session | None:
    """Project a device-reported state onto the backend session state machine."""
    if session is None or not session_is_open(session):
        return session

    normalized = str(state or "").strip().lower()
    if normalized in START_CHARGING_STATUSES or normalized == ChargeSessionState.CHARGING:
        return set_session_state(session, ChargeSessionState.CHARGING, now=now)
    if normalized in {ChargeSessionState.WAITING_PLUG, "waiting_cable", "reserved", "ready"}:
        return set_session_state(session, ChargeSessionState.WAITING_PLUG, now=now)
    if normalized in {"idle", "stopped"}:
        return mark_stop_requested(session, now=now)
    if normalized in ERROR_STATES or normalized == ChargeSessionState.ERROR:
        return mark_error(session, now=now)
    return session


def mark_state_from_ack(
    session: Session | None,
    *,
    action: str,
    ack_status: str,
    now=None,
) -> Session | None:
    """Project an ESP32 ACK onto the backend session state machine."""
    normalized_action = str(action or "").strip().upper()
    normalized_status = str(ack_status or "").strip().lower()
    if normalized_action == "START":
        return mark_start_ack(session, normalized_status, now=now)
    if normalized_action == "UNLOCK":
        if normalized_status in ERROR_STATES:
            return mark_error(session, now=now)
        if normalized_status in UNLOCK_WAITING_STATUSES:
            return set_session_state(session, ChargeSessionState.WAITING_PLUG, now=now)
    if normalized_action == "STOP" and normalized_status in STOP_ACK_STATUSES | ERROR_STATES:
        if normalized_status in ERROR_STATES:
            return mark_error(session, now=now)
        return mark_stop_requested(session, now=now)
    return session
