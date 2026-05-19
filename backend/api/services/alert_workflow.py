from __future__ import annotations

from django.utils import timezone

from api.models import Alerte, AlertStatus, Technicien


TERMINAL_ALERT_STATUSES = {
    AlertStatus.RESOLVED,
    "resolved",
    AlertStatus.CLOSED,
    AlertStatus.FERMEE,
}


class AlertWorkflowError(ValueError):
    """Raised when an alert lifecycle transition is not allowed."""


def alert_location(alert: Alerte):
    """Return the station, cabinet and charging bay linked to an alert."""
    session = alert.session
    data = alert.data
    device = data.capteur.device if data and data.capteur else None
    emplacement = session.emplacement if session else device.emplacement if device else None
    station = emplacement.station if emplacement else None
    borne = emplacement.borne if emplacement else None
    return station, borne, emplacement


def alert_station_id(alert: Alerte):
    """Return the station id that scopes technician access to this alert."""
    station, _borne, _emplacement = alert_location(alert)
    return station.id_station if station else None


def alert_queryset():
    """Return alerts with all relations needed for location and workflow checks."""
    return Alerte.objects.select_related(
        "assigned_technician",
        "acknowledged_by",
        "resolved_by",
        "data",
        "data__capteur",
        "data__capteur__device",
        "data__capteur__device__emplacement",
        "data__capteur__device__emplacement__station",
        "data__capteur__device__emplacement__borne",
        "session",
        "session__emplacement",
        "session__emplacement__station",
        "session__emplacement__borne",
    )


def acknowledge_alert(alert: Alerte, technician: Technicien | None, *, now=None) -> Alerte:
    """Mark an active operational alert as taken in charge."""
    if alert.status in TERMINAL_ALERT_STATUSES:
        raise AlertWorkflowError("Une alerte résolue ou fermée ne peut pas être prise en charge.")

    now = now or timezone.now()
    alert.status = AlertStatus.IN_PROGRESS
    if technician is not None:
        alert.assigned_technician = alert.assigned_technician or technician
        alert.acknowledged_by = technician
    alert.acknowledged_at = alert.acknowledged_at or now
    alert.last_seen = now
    alert.save(
        update_fields=[
            "status",
            "assigned_technician",
            "acknowledged_by",
            "acknowledged_at",
            "last_seen",
        ]
    )
    return alert


def resolve_alert(
    alert: Alerte,
    technician: Technicien | None,
    *,
    note: str = "",
    now=None,
) -> Alerte:
    """Resolve an operational alert after technician or admin handling."""
    if alert.status in {AlertStatus.CLOSED, AlertStatus.FERMEE}:
        raise AlertWorkflowError("Une alerte fermée ne peut plus être modifiée.")

    now = now or timezone.now()
    if technician is not None:
        alert.assigned_technician = alert.assigned_technician or technician
        alert.resolved_by = technician
        if alert.acknowledged_by_id is None:
            alert.acknowledged_by = technician
        if alert.acknowledged_at is None:
            alert.acknowledged_at = now
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = now
    alert.last_seen = now
    alert.resolution_note = str(note or "").strip()
    alert.save(
        update_fields=[
            "status",
            "assigned_technician",
            "acknowledged_by",
            "acknowledged_at",
            "resolved_by",
            "resolved_at",
            "last_seen",
            "resolution_note",
        ]
    )
    return alert
