"""Local Raspberry charge state guard.

The backend remains the source of truth for reservations and sessions. This
module only protects the edge device against duplicate physical commands for the
same slot while the kiosk is operating.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IDLE = "idle"
RESERVED = "reserved"
ACCESS_VALIDATED = "access_validated"
WAITING_PLUG = "waiting_plug"
CHARGING = "charging"
STOPPING = "stopping"
STOPPED = "stopped"
ERROR = "error"

LEGACY_STATE_ALIASES = {
    "waiting_cable": WAITING_PLUG,
}

ACTIVE_STATES = {RESERVED, ACCESS_VALIDATED, WAITING_PLUG, CHARGING, STOPPING}
TERMINAL_STATES = {IDLE, STOPPED}
KNOWN_STATES = ACTIVE_STATES | TERMINAL_STATES | {ERROR}


class ChargeStateError(RuntimeError):
    """Raised when a local charge transition is not allowed."""


@dataclass(frozen=True)
class ChargeStateSnapshot:
    """Serializable state snapshot for one slot."""

    slot_id: str
    state: str
    session_id: str = ""
    station: str = ""
    borne: str = ""
    emplacement: str = ""
    updated_at: str = ""
    detail: str = ""
    payload: dict[str, Any] | None = None

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "state": self.state,
            "active": self.active,
            "session_id": self.session_id,
            "station": self.station,
            "borne": self.borne,
            "emplacement": self.emplacement,
            "updated_at": self.updated_at,
            "detail": self.detail,
            "payload": self.payload or {},
        }


def default_db_path() -> Path:
    configured = os.environ.get("CHARGE_STATE_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "charge_state.sqlite3"


class ChargeStateStore:
    """SQLite-backed local state machine for Raspberry slot commands."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self):
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS charge_state (
                    slot_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    session_id TEXT NOT NULL DEFAULT '',
                    station TEXT NOT NULL DEFAULT '',
                    borne TEXT NOT NULL DEFAULT '',
                    emplacement TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.commit()

    def snapshot(self, slot_id: str) -> ChargeStateSnapshot:
        normalized_slot = self._normalize_slot(slot_id)
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM charge_state WHERE slot_id = ?",
                (normalized_slot,),
            ).fetchone()
        return self._snapshot_from_row(row, slot_id=normalized_slot)

    def all_snapshots(self) -> list[ChargeStateSnapshot]:
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM charge_state ORDER BY slot_id"
            ).fetchall()
        return [self._snapshot_from_row(row) for row in rows]

    def start_requested(
        self,
        *,
        slot_id: str,
        session_id: str,
        station: str = "",
        borne: str = "",
        emplacement: str = "",
        detail: str = "START demande par le kiosk.",
    ) -> ChargeStateSnapshot:
        normalized_slot = self._normalize_slot(slot_id)
        normalized_session = self._normalize_session(session_id)
        with self._lock, closing(self._connect()) as connection:
            current = self._get_snapshot(connection, normalized_slot)
            if current.active:
                raise ChargeStateError(
                    "Une charge est déjà active sur cet emplacement."
                )
            if current.state == ERROR:
                raise ChargeStateError(
                    "Emplacement en erreur locale. Verification technicien requise."
                )
            return self._write_snapshot(
                connection,
                slot_id=normalized_slot,
                state=ACCESS_VALIDATED,
                session_id=normalized_session,
                station=station,
                borne=borne,
                emplacement=emplacement,
                detail=detail,
            )

    def stop_requested(
        self,
        *,
        slot_id: str,
        session_id: str,
        detail: str = "STOP demande par le kiosk.",
    ) -> ChargeStateSnapshot:
        normalized_slot = self._normalize_slot(slot_id)
        normalized_session = self._normalize_session(session_id)
        with self._lock, closing(self._connect()) as connection:
            current = self._get_snapshot(connection, normalized_slot)
            self._ensure_session_matches(current, normalized_session)
            if current.state in TERMINAL_STATES:
                raise ChargeStateError("Aucune charge active sur cet emplacement.")
            if current.state == ERROR:
                raise ChargeStateError(
                    "Emplacement en erreur locale. Verification technicien requise."
                )
            return self._write_snapshot(
                connection,
                slot_id=normalized_slot,
                state=STOPPING,
                session_id=normalized_session,
                station=current.station,
                borne=current.borne,
                emplacement=current.emplacement,
                detail=detail,
                payload=current.payload or {},
            )

    def command_recorded(
        self,
        *,
        slot_id: str,
        action: str,
        session_id: str,
        mqtt_result: dict[str, Any] | None = None,
    ) -> ChargeStateSnapshot:
        normalized_slot = self._normalize_slot(slot_id)
        normalized_session = self._normalize_session(session_id)
        normalized_action = str(action or "").strip().upper()
        with self._lock, closing(self._connect()) as connection:
            current = self._get_snapshot(connection, normalized_slot)
            self._ensure_session_matches(current, normalized_session)
            next_state, detail = self._state_after_command(
                current=current,
                action=normalized_action,
                mqtt_result=mqtt_result or {},
            )
            return self._write_snapshot(
                connection,
                slot_id=normalized_slot,
                state=next_state,
                session_id=normalized_session,
                station=current.station,
                borne=current.borne,
                emplacement=current.emplacement,
                detail=detail,
                payload=mqtt_result or {},
            )

    def mark_error(
        self,
        *,
        slot_id: str,
        session_id: str = "",
        detail: str,
        payload: dict[str, Any] | None = None,
    ) -> ChargeStateSnapshot:
        normalized_slot = self._normalize_slot(slot_id)
        normalized_session = str(session_id or "").strip()
        with self._lock, closing(self._connect()) as connection:
            current = self._get_snapshot(connection, normalized_slot)
            if normalized_session and current.session_id:
                self._ensure_session_matches(current, normalized_session)
            return self._write_snapshot(
                connection,
                slot_id=normalized_slot,
                state=ERROR,
                session_id=normalized_session or current.session_id,
                station=current.station,
                borne=current.borne,
                emplacement=current.emplacement,
                detail=detail,
                payload=payload or current.payload or {},
            )

    def reset_slot(
        self,
        *,
        slot_id: str,
        detail: str = "Etat local reinitialise.",
    ) -> ChargeStateSnapshot:
        normalized_slot = self._normalize_slot(slot_id)
        with self._lock, closing(self._connect()) as connection:
            return self._write_snapshot(
                connection,
                slot_id=normalized_slot,
                state=IDLE,
                detail=detail,
            )

    def _state_after_command(
        self,
        *,
        current: ChargeStateSnapshot,
        action: str,
        mqtt_result: dict[str, Any],
    ) -> tuple[str, str]:
        if action == "START":
            status = str(mqtt_result.get("ack_status") or "").strip().lower()
            if status in {"charging", "charging_started"}:
                return CHARGING, "START confirmé, charge active."
            if mqtt_result.get("command_confirmed"):
                return WAITING_PLUG, "START confirmé, attente câble et boîtier fermé."
            return current.state, "START publie, confirmation ESP32 non exigee."

        if action == "STOP":
            if mqtt_result.get("command_confirmed") or not mqtt_result.get("ack_required"):
                return STOPPED, "STOP confirmé ou accepté sans ACK obligatoire."
            return STOPPING, "STOP publie, attente confirmation ESP32."

        return current.state, f"Commande {action} publiee."

    def _get_snapshot(self, connection, slot_id: str) -> ChargeStateSnapshot:
        row = connection.execute(
            "SELECT * FROM charge_state WHERE slot_id = ?",
            (slot_id,),
        ).fetchone()
        return self._snapshot_from_row(row, slot_id=slot_id)

    def _write_snapshot(
        self,
        connection,
        *,
        slot_id: str,
        state: str,
        session_id: str = "",
        station: str = "",
        borne: str = "",
        emplacement: str = "",
        detail: str = "",
        payload: dict[str, Any] | None = None,
    ) -> ChargeStateSnapshot:
        state = LEGACY_STATE_ALIASES.get(state, state)
        if state not in KNOWN_STATES:
            raise ChargeStateError(f"Etat de charge inconnu: {state}.")
        updated_at = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload or {}, ensure_ascii=True)
        connection.execute(
            """
            INSERT INTO charge_state (
                slot_id, state, session_id, station, borne, emplacement,
                updated_at, detail, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slot_id) DO UPDATE SET
                state = excluded.state,
                session_id = excluded.session_id,
                station = excluded.station,
                borne = excluded.borne,
                emplacement = excluded.emplacement,
                updated_at = excluded.updated_at,
                detail = excluded.detail,
                payload_json = excluded.payload_json
            """,
            (
                slot_id,
                state,
                str(session_id or "").strip(),
                str(station or "").strip(),
                str(borne or "").strip(),
                str(emplacement or "").strip(),
                updated_at,
                str(detail or "").strip(),
                payload_json,
            ),
        )
        connection.commit()
        return ChargeStateSnapshot(
            slot_id=slot_id,
            state=state,
            session_id=str(session_id or "").strip(),
            station=str(station or "").strip(),
            borne=str(borne or "").strip(),
            emplacement=str(emplacement or "").strip(),
            updated_at=updated_at,
            detail=str(detail or "").strip(),
            payload=payload or {},
        )

    def _snapshot_from_row(
        self,
        row,
        *,
        slot_id: str = "",
    ) -> ChargeStateSnapshot:
        if row is None:
            return ChargeStateSnapshot(slot_id=slot_id, state=IDLE)
        state = LEGACY_STATE_ALIASES.get(row["state"], row["state"])
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        return ChargeStateSnapshot(
            slot_id=row["slot_id"],
            state=state,
            session_id=row["session_id"],
            station=row["station"],
            borne=row["borne"],
            emplacement=row["emplacement"],
            updated_at=row["updated_at"],
            detail=row["detail"],
            payload=payload,
        )

    def _ensure_session_matches(
        self,
        current: ChargeStateSnapshot,
        session_id: str,
    ) -> None:
        if not session_id:
            raise ChargeStateError("Session de charge manquante.")
        if current.session_id and current.session_id != session_id:
            raise ChargeStateError(
                "Cet emplacement est lie a une autre session locale."
            )

    def _normalize_slot(self, slot_id: str) -> str:
        normalized = str(slot_id or "").strip()
        if not normalized:
            raise ChargeStateError("Emplacement MQTT manquant.")
        return normalized

    def _normalize_session(self, session_id: str) -> str:
        normalized = str(session_id or "").strip()
        if not normalized:
            raise ChargeStateError("Session de charge manquante.")
        return normalized
