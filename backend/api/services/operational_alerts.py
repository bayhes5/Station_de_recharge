from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.models import Alerte, AlertStatus, Session, SessionTelemetry
from api.services.email_notifications import notify_technicians_for_alert


RESOLVED_ALERT_STATUSES = {"resolved", "resolue", "closed", "fermee"}
PRESERVED_ACTIVE_ALERT_STATUSES = {AlertStatus.IN_PROGRESS}
SESSION_WITHOUT_TELEMETRY = "session_without_telemetry"


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


def _session_location_label(session: Session) -> str:
    """Return a readable physical location for alert messages."""
    emplacement = session.emplacement
    station = emplacement.station
    borne = emplacement.borne
    return f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}"


def _open_session_telemetry_alerts():
    """Return unresolved session telemetry alerts."""
    return (
        Alerte.objects.select_related(
            "session",
            "session__emplacement",
            "session__emplacement__station",
            "session__emplacement__borne",
        )
        .filter(type=SESSION_WITHOUT_TELEMETRY)
        .exclude(status__in=RESOLVED_ALERT_STATUSES)
    )


def _upsert_session_telemetry_alert(session: Session, now) -> bool:
    """Create or update the alert for one stale active session."""
    message = (
        "Session active sans télémétrie récente sur "
        f"{_session_location_label(session)}."
    )
    existing = _open_session_telemetry_alerts().filter(session=session).first()
    if existing:
        existing.message = message
        existing.niveau_severite = "haute"
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
        type=SESSION_WITHOUT_TELEMETRY,
        message=message,
        niveau_severite="haute",
        status="nouvelle",
        timestamp=now,
        first_seen=now,
        last_seen=now,
    )
    transaction.on_commit(
        lambda alert_id=alert.id_alerte: notify_technicians_for_alert(alert_id)
    )
    return True


def _resolve_non_stale_session_alerts(stale_session_ids: set, now) -> int:
    """Resolve stale-session alerts whose session recovered or ended."""
    resolved = 0
    for alert in _open_session_telemetry_alerts():
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
    """Create and resolve alerts for active sessions missing telemetry."""
    now = now or timezone.now()
    cutoff = now - _telemetry_stale_delta()
    stale_sessions = list(
        Session.objects.select_related(
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
        )
        .filter(end_time__isnull=True, start_time__lte=cutoff)
        .exclude(telemetries__timestamp__gte=cutoff)
        .distinct()
    )
    stale_session_ids = {session.id_session for session in stale_sessions}

    created = 0
    updated = 0
    for session in stale_sessions:
        if _upsert_session_telemetry_alert(session, now):
            created += 1
        else:
            updated += 1

    resolved = _resolve_non_stale_session_alerts(stale_session_ids, now)
    return OperationalAlertScanResult(created=created, updated=updated, resolved=resolved)


def latest_session_telemetry_at(session: Session):
    """Return the latest telemetry timestamp for display or diagnostics."""
    return (
        SessionTelemetry.objects.filter(session=session)
        .order_by("-timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )
