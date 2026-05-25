from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.models import Alerte, AlertStatus, ChargeSessionState, Session, SessionTelemetry
from api.services.email_notifications import notify_technicians_for_alert


RESOLVED_ALERT_STATUSES = {"resolved", "resolue", "closed", "fermee"}
PRESERVED_ACTIVE_ALERT_STATUSES = {AlertStatus.IN_PROGRESS}
SESSION_WITHOUT_TELEMETRY = "session_without_telemetry"
SESSION_STOPPING_TOO_LONG = "session_stopping_too_long"


@dataclass(frozen=True)
class OperationalAlertScanResult:
    """Summarize one operational alert scan."""

    created: int = 0
    updated: int = 0
    resolved: int = 0


def _telemetry_stale_delta() -> timedelta:
    """Return the tolerated telemetry silence for an active charging session."""
    minutes = getattr(settings, "SESSION_TELEMETRY_STALE_MINUTES", 2)
    return timedelta(minutes=max(1, int(minutes)))


def _stopping_stale_delta() -> timedelta:
    """Return the tolerated time for a session waiting for backend closure."""
    minutes = getattr(settings, "SESSION_STOPPING_STALE_MINUTES", 2)
    return timedelta(minutes=max(1, int(minutes)))


def _session_location_label(session: Session) -> str:
    """Return a readable physical location for alert messages."""
    emplacement = session.emplacement
    station = emplacement.station
    borne = emplacement.borne
    return f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}"


def _open_session_telemetry_alerts():
    """Return unresolved session telemetry alerts."""
    return _open_session_alerts(SESSION_WITHOUT_TELEMETRY)


def _open_stopping_alerts():
    """Return unresolved alerts for sessions stuck in stopping state."""
    return _open_session_alerts(SESSION_STOPPING_TOO_LONG)


def _open_session_alerts(alert_type: str):
    """Return unresolved alerts linked to charging sessions."""
    return (
        Alerte.objects.select_related(
            "session",
            "session__emplacement",
            "session__emplacement__station",
            "session__emplacement__borne",
        )
        .filter(type=alert_type)
        .exclude(status__in=RESOLVED_ALERT_STATUSES)
    )


def _upsert_session_alert(
    *,
    session: Session,
    now,
    alert_type: str,
    message: str,
    severity: str = "haute",
) -> bool:
    """Create or update one session-level operational alert."""
    existing = _open_session_alerts(alert_type).filter(session=session).first()
    if existing:
        existing.message = message
        existing.niveau_severite = severity
        if existing.status not in PRESERVED_ACTIVE_ALERT_STATUSES:
            existing.status = "active"
        existing.timestamp = now
        existing.last_seen = now
        existing.save(
            update_fields=[
                "message",
                "niveau_severite",
                "status",
                "timestamp",
                "last_seen",
            ]
        )
        transaction.on_commit(
            lambda alert_id=existing.id_alerte: notify_technicians_for_alert(alert_id)
        )
        return False

    alert = Alerte.objects.create(
        session=session,
        type=alert_type,
        message=message,
        niveau_severite=severity,
        status="nouvelle",
        timestamp=now,
        first_seen=now,
        last_seen=now,
    )
    transaction.on_commit(
        lambda alert_id=alert.id_alerte: notify_technicians_for_alert(alert_id)
    )
    return True


def _upsert_session_telemetry_alert(session: Session, now) -> bool:
    """Create or update the alert for one stale active session."""
    return _upsert_session_alert(
        session=session,
        now=now,
        alert_type=SESSION_WITHOUT_TELEMETRY,
        message=f"Session active sans télémétrie récente sur {_session_location_label(session)}.",
    )


def _upsert_stopping_alert(session: Session, now) -> bool:
    """Create or update the alert for one session stuck in stopping state."""
    return _upsert_session_alert(
        session=session,
        now=now,
        alert_type=SESSION_STOPPING_TOO_LONG,
        message=(
            "Session en arrêt depuis trop longtemps sur "
            f"{_session_location_label(session)}. Vérifier l'ACK STOP, le kiosque "
            "et la clôture backend."
        ),
    )


def _resolve_non_stale_alerts(open_alerts, stale_session_ids: set, now) -> int:
    """Resolve alerts whose session recovered or ended."""
    resolved = 0
    for alert in open_alerts():
        if alert.session_id in stale_session_ids:
            continue
        alert.status = "resolue"
        alert.timestamp = now
        alert.last_seen = now
        alert.resolved_at = now
        alert.save(update_fields=["status", "timestamp", "last_seen", "resolved_at"])
        resolved += 1
    return resolved


@transaction.atomic
def scan_session_telemetry_gaps(now=None) -> OperationalAlertScanResult:
    """Create and resolve alerts for stale active sessions."""
    now = now or timezone.now()
    cutoff = now - _telemetry_stale_delta()
    stale_sessions = list(
        Session.objects.select_related(
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
        )
        .filter(end_time__isnull=True, start_time__lte=cutoff)
        .exclude(charge_state=ChargeSessionState.STOPPING)
        .exclude(telemetries__timestamp__gte=cutoff)
        .distinct()
    )
    stale_session_ids = {session.id_session for session in stale_sessions}

    stopping_cutoff = now - _stopping_stale_delta()
    stale_stopping_sessions = list(
        Session.objects.select_related(
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
        )
        .filter(
            end_time__isnull=True,
            charge_state=ChargeSessionState.STOPPING,
            charge_state_updated_at__lte=stopping_cutoff,
        )
        .distinct()
    )
    stale_stopping_session_ids = {
        session.id_session for session in stale_stopping_sessions
    }

    created = 0
    updated = 0
    for session in stale_sessions:
        if _upsert_session_telemetry_alert(session, now):
            created += 1
        else:
            updated += 1

    for session in stale_stopping_sessions:
        if _upsert_stopping_alert(session, now):
            created += 1
        else:
            updated += 1

    resolved = _resolve_non_stale_alerts(
        _open_session_telemetry_alerts,
        stale_session_ids,
        now,
    )
    resolved += _resolve_non_stale_alerts(
        _open_stopping_alerts,
        stale_stopping_session_ids,
        now,
    )
    return OperationalAlertScanResult(created=created, updated=updated, resolved=resolved)


def latest_session_telemetry_at(session: Session):
    """Return the latest telemetry timestamp for display or diagnostics."""
    return (
        SessionTelemetry.objects.filter(session=session)
        .order_by("-timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )
