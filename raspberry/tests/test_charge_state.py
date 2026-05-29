import sys
import uuid
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from charge_state import (  # noqa: E402
    ACCESS_VALIDATED,
    CHARGING,
    ERROR,
    IDLE,
    STOPPED,
    WAITING_PLUG,
    ChargeStateError,
    ChargeStateStore,
)


@pytest.fixture
def store(request):
    state_dir = Path(__file__).resolve().parent / ".state_tmp"
    state_dir.mkdir(exist_ok=True)
    db_path = state_dir / f"{uuid.uuid4().hex}.sqlite3"

    def cleanup():
        db_path.unlink(missing_ok=True)
        try:
            state_dir.rmdir()
        except OSError:
            # Another store fixture may still be using the shared temp dir.
            pass

    request.addfinalizer(cleanup)
    return ChargeStateStore(db_path)


def test_start_records_waiting_plug_after_confirmed_ack(store):
    snapshot = store.start_requested(
        slot_id="slot1",
        session_id="session-1",
        station="Station A",
        borne="Borne 1",
        emplacement="1",
    )

    assert snapshot.state == ACCESS_VALIDATED
    assert snapshot.active is True

    confirmed = store.command_recorded(
        slot_id="slot1",
        action="START",
        session_id="session-1",
        mqtt_result={
            "ack_required": True,
            "ack_received": True,
            "ack_status": "accepted",
            "command_confirmed": True,
        },
    )

    assert confirmed.state == WAITING_PLUG
    assert confirmed.session_id == "session-1"
    assert confirmed.station == "Station A"


def test_start_moves_directly_to_charging_when_ack_reports_charge(store):
    store.start_requested(slot_id="slot1", session_id="session-1")

    snapshot = store.command_recorded(
        slot_id="slot1",
        action="START",
        session_id="session-1",
        mqtt_result={
            "ack_required": True,
            "ack_status": "charging_started",
            "command_confirmed": True,
        },
    )

    assert snapshot.state == CHARGING


def test_legacy_waiting_cable_state_is_reported_as_waiting_plug(store):
    store.start_requested(slot_id="slot1", session_id="session-1")
    store.command_recorded(
        slot_id="slot1",
        action="START",
        session_id="session-1",
        mqtt_result={
            "ack_required": True,
            "ack_status": "accepted",
            "command_confirmed": True,
        },
    )
    connection = store._connect()  # noqa: SLF001 - compatibility check.
    try:
        connection.execute(
            "UPDATE charge_state SET state = ? WHERE slot_id = ?",
            ("waiting_cable", "slot1"),
        )
        connection.commit()
    finally:
        connection.close()

    assert store.snapshot("slot1").state == WAITING_PLUG


def test_duplicate_start_is_rejected_while_slot_is_active(store):
    store.start_requested(slot_id="slot1", session_id="session-1")

    with pytest.raises(ChargeStateError, match="déjà active"):
        store.start_requested(slot_id="slot1", session_id="session-1")

    with pytest.raises(ChargeStateError, match="déjà active"):
        store.start_requested(slot_id="slot1", session_id="session-2")


def test_stop_requires_matching_active_session(store):
    store.start_requested(slot_id="slot1", session_id="session-1")

    with pytest.raises(ChargeStateError, match="autre session"):
        store.stop_requested(slot_id="slot1", session_id="session-2")


def test_stop_closes_slot_after_confirmed_ack(store):
    store.start_requested(slot_id="slot1", session_id="session-1")
    stopping = store.stop_requested(slot_id="slot1", session_id="session-1")

    assert stopping.state == "stopping"
    assert stopping.active is True

    stopped = store.command_recorded(
        slot_id="slot1",
        action="STOP",
        session_id="session-1",
        mqtt_result={
            "ack_required": True,
            "ack_status": "stopped",
            "command_confirmed": True,
        },
    )

    assert stopped.state == STOPPED
    assert stopped.active is False


def test_error_state_blocks_new_start_until_reset(store):
    store.mark_error(slot_id="slot1", session_id="session-1", detail="ACK invalide.")

    snapshot = store.snapshot("slot1")
    assert snapshot.state == ERROR

    with pytest.raises(ChargeStateError, match="erreur locale"):
        store.start_requested(slot_id="slot1", session_id="session-2")

    reset = store.reset_slot(slot_id="slot1")
    assert reset.state == IDLE
    store.start_requested(slot_id="slot1", session_id="session-2")
