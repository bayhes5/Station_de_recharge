from __future__ import annotations

import csv
import json
from datetime import datetime, time
from io import StringIO

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import (
    Alerte,
    Borne,
    Device,
    Emplacement,
    JournalSecurite,
    Reservation,
    Session,
    Station,
)
from api.permissions import IsStaffUser
from api.services.supervision import RESOLVED_ALERT_STATUSES, device_is_online


MAX_EXPORT_ROWS = 1000


OPERATIONAL_CSV_COLUMNS = [
    "station",
    "borne",
    "emplacement",
    "statut_emplacement",
    "serrure",
    "esp32",
    "statut_esp32",
    "firmware",
    "firmware_attendu",
    "conformite_firmware",
    "derniere_telemetrie",
    "session_active",
    "etat_session",
    "reservations_periode",
    "sessions_periode",
    "alertes_actives",
]

SECURITY_LOG_CSV_COLUMNS = [
    "date_action",
    "utilisateur",
    "action",
    "statut",
    "ip",
]

EXPORT_DATASETS = {
    "operational": {
        "label": "Instantané opérationnel",
        "columns": OPERATIONAL_CSV_COLUMNS,
        "filename": "export-operationnel",
    },
    "security_logs": {
        "label": "Journaux de sécurité archivés",
        "columns": SECURITY_LOG_CSV_COLUMNS,
        "filename": "journaux-securite-archives",
    },
}


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_operational_export(request):
    """Export an operational snapshot for administration and audit."""
    filters = _parse_filters(request)
    dataset = filters["dataset"]
    if dataset == "security_logs":
        payload = build_security_log_export_payload(filters=filters)
    else:
        payload = build_operational_export_payload(filters=filters)

    export_format = request.query_params.get("export_format", request.query_params.get("format", "json")).lower()
    is_download = request.query_params.get("download") in {"1", "true", "yes"}
    if is_download:
        _record_export_event(request, payload)

    if export_format == "csv":
        return _csv_response(
            payload["rows"],
            payload["metadata"]["columns"],
            filename=f'{payload["metadata"]["filename"]}.csv',
        )
    if is_download:
        return _json_download_response(
            payload,
            filename=f'{payload["metadata"]["filename"]}.json',
        )
    return Response(payload)


def build_operational_export_payload(filters=None):
    """Build a compact station/cabinet/bay snapshot suitable for JSON or CSV."""
    filters = filters or {}
    now = timezone.now()
    emplacements = list(_emplacement_queryset(filters))
    rows = [_serialize_emplacement(row, now, filters) for row in emplacements]
    reservations = _scoped_reservations(filters)
    sessions = _scoped_sessions(filters)
    alerts = _scoped_alerts(filters)
    summary = {
        "generated_at": now.isoformat(),
        "filters": _serialize_filters(filters),
        "stations_total": _station_queryset(filters).count(),
        "bornes_total": _borne_queryset(filters).count(),
        "emplacements_total": len(emplacements),
        "devices_total": Device.objects.filter(emplacement__in=emplacements).count(),
        "devices_online": sum(1 for row in rows if row["statut_esp32"] != "hors_ligne"),
        "active_sessions": sessions.filter(end_time__isnull=True).exclude(charge_state="stopped").count(),
        "archived_sessions": sessions.filter(end_time__isnull=False).count(),
        "upcoming_reservations": reservations.filter(date_debut__gte=now).count(),
        "reservations_in_period": reservations.count(),
        "sessions_in_period": sessions.count(),
        "active_alerts": alerts.exclude(status__in=RESOLVED_ALERT_STATUSES).count(),
    }
    return {
        "metadata": _dataset_metadata("operational"),
        "summary": summary,
        "rows": rows[:MAX_EXPORT_ROWS],
    }


def build_security_log_export_payload(filters=None):
    """Build a filtered security-log archive for preview or export."""
    filters = filters or {}
    queryset = _security_log_queryset(filters)
    total_matches = queryset.count()
    rows = [_serialize_security_log(row) for row in queryset[:MAX_EXPORT_ROWS]]
    summary = {
        "generated_at": timezone.now().isoformat(),
        "filters": _serialize_filters(filters),
        "total_matches": total_matches,
        "exported_rows": len(rows),
        "limited": total_matches > len(rows),
    }
    return {
        "metadata": _dataset_metadata("security_logs"),
        "summary": summary,
        "rows": rows,
    }


def _emplacement_queryset(filters):
    """Return charging slots scoped by the selected station filter."""
    queryset = (
        Emplacement.objects.select_related("station", "borne", "device")
        .prefetch_related("sessions", "device__capteurs")
    )
    if filters.get("station_id"):
        queryset = queryset.filter(station_id=filters["station_id"])
    return queryset.order_by("station__nom", "borne__numero", "numero")


def _serialize_emplacement(emplacement, now, filters):
    """Serialize one slot with current device, session and alert context."""
    device = getattr(emplacement, "device", None)
    active_session = (
        emplacement.sessions.filter(end_time__isnull=True)
        .exclude(charge_state="stopped")
        .order_by("-start_time")
        .first()
    )
    active_alerts = _active_alert_count(emplacement)
    return {
        "station": emplacement.station.nom,
        "borne": emplacement.borne.nom,
        "emplacement": emplacement.numero,
        "statut_emplacement": emplacement.statut,
        "serrure": emplacement.lock_state,
        "esp32": device.slot_id if device else "",
        "statut_esp32": _device_status(device, now),
        "firmware": device.firmware_version if device else "",
        "firmware_attendu": device.expected_firmware_version if device else "",
        "conformite_firmware": device.firmware_update_status if device else "",
        "derniere_telemetrie": device.last_seen.isoformat() if device and device.last_seen else "",
        "session_active": str(active_session.id_session) if active_session else "",
        "etat_session": active_session.charge_state if active_session else "",
        "reservations_periode": _scoped_reservations(filters).filter(emplacement=emplacement).count(),
        "sessions_periode": _scoped_sessions(filters).filter(emplacement=emplacement).count(),
        "alertes_actives": active_alerts,
    }


def _device_status(device, now):
    """Return the user-facing online status for an ESP32 device."""
    if device is None:
        return ""
    if not device_is_online(device, now=now):
        return "hors_ligne"
    return device.status


def _active_alert_count(emplacement):
    """Count unresolved alerts linked to a slot through sessions or telemetry."""
    return (
        Alerte.objects.exclude(status__in=RESOLVED_ALERT_STATUSES)
        .filter(
            Q(session__emplacement=emplacement)
            | Q(data__capteur__device__emplacement=emplacement)
        )
        .count()
    )


def _parse_filters(request):
    """Parse export filters from query parameters."""
    date_from, date_to = _parse_date_range(
        request.query_params.get("date_from"),
        request.query_params.get("date_to"),
    )
    dataset = request.query_params.get("dataset", "operational")
    if dataset not in EXPORT_DATASETS:
        dataset = "operational"
    return {
        "dataset": dataset,
        "station_id": request.query_params.get("station_id") or "",
        "date_from": date_from,
        "date_to": date_to,
        "query": (request.query_params.get("query") or "").strip(),
        "log_status": (request.query_params.get("log_status") or "").strip(),
    }


def _parse_date_range(raw_from, raw_to):
    """Convert optional date strings to aware datetime bounds."""
    date_from = parse_date(raw_from or "")
    date_to = parse_date(raw_to or "")
    start = timezone.make_aware(datetime.combine(date_from, time.min)) if date_from else None
    end = timezone.make_aware(datetime.combine(date_to, time.max)) if date_to else None
    return start, end


def _serialize_filters(filters):
    """Serialize filters in a stable JSON-compatible shape."""
    return {
        "dataset": filters.get("dataset") or "operational",
        "station_id": filters.get("station_id") or "",
        "date_from": filters.get("date_from").isoformat() if filters.get("date_from") else "",
        "date_to": filters.get("date_to").isoformat() if filters.get("date_to") else "",
        "query": filters.get("query") or "",
        "log_status": filters.get("log_status") or "",
    }


def _station_queryset(filters):
    """Return stations scoped by the optional station identifier."""
    queryset = Station.objects.all()
    if filters.get("station_id"):
        queryset = queryset.filter(id_station=filters["station_id"])
    return queryset


def _borne_queryset(filters):
    """Return cabinets scoped by the optional station identifier."""
    queryset = Borne.objects.all()
    if filters.get("station_id"):
        queryset = queryset.filter(station_id=filters["station_id"])
    return queryset


def _scoped_reservations(filters):
    """Return reservations overlapping the selected station and period."""
    queryset = Reservation.objects.all()
    if filters.get("station_id"):
        queryset = queryset.filter(emplacement__station_id=filters["station_id"])
    if filters.get("date_from"):
        queryset = queryset.filter(date_fin__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(date_debut__lte=filters["date_to"])
    return queryset


def _scoped_sessions(filters):
    """Return sessions overlapping the selected station and period."""
    queryset = Session.objects.all()
    if filters.get("station_id"):
        queryset = queryset.filter(emplacement__station_id=filters["station_id"])
    if filters.get("date_from"):
        queryset = queryset.filter(Q(end_time__isnull=True) | Q(end_time__gte=filters["date_from"]))
    if filters.get("date_to"):
        queryset = queryset.filter(start_time__lte=filters["date_to"])
    return queryset


def _scoped_alerts(filters):
    """Return alerts scoped by station and timestamp filters."""
    queryset = Alerte.objects.all()
    if filters.get("station_id"):
        queryset = queryset.filter(
            Q(session__emplacement__station_id=filters["station_id"])
            | Q(data__capteur__device__emplacement__station_id=filters["station_id"])
        )
    if filters.get("date_from"):
        queryset = queryset.filter(timestamp__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(timestamp__lte=filters["date_to"])
    return queryset


def _security_log_queryset(filters):
    """Return archived security logs matching export filters."""
    queryset = JournalSecurite.objects.select_related("utilisateur").order_by("-date_action")
    if filters.get("date_from"):
        queryset = queryset.filter(date_action__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(date_action__lte=filters["date_to"])
    if filters.get("log_status"):
        queryset = queryset.filter(statut=filters["log_status"])
    if filters.get("query"):
        query = filters["query"]
        queryset = queryset.filter(
            Q(action__icontains=query)
            | Q(ip__icontains=query)
            | Q(utilisateur__pseudo__icontains=query)
            | Q(utilisateur__email__icontains=query)
        )
    return queryset


def _serialize_security_log(log):
    """Serialize one security log row for preview or CSV export."""
    user = log.utilisateur
    return {
        "date_action": log.date_action.isoformat() if log.date_action else "",
        "utilisateur": getattr(user, "pseudo", "") or "Compte supprimé",
        "action": log.action,
        "statut": log.statut,
        "ip": log.ip,
    }


def _dataset_metadata(dataset):
    """Return static metadata for an export dataset."""
    config = EXPORT_DATASETS[dataset]
    return {
        "dataset": dataset,
        "label": config["label"],
        "columns": config["columns"],
        "filename": config["filename"],
        "max_rows": MAX_EXPORT_ROWS,
    }


def _request_ip(request):
    """Extract the client IP address used for audit logging."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def _record_export_event(request, payload):
    """Record a security log entry when an administrator downloads an export."""
    metadata = payload["metadata"]
    JournalSecurite.objects.create(
        utilisateur=request.user,
        action=(
            f"admin:{request.user.pseudo}:export:{metadata['dataset']}:"
            f"{len(payload['rows'])}_rows"
        ),
        ip=_request_ip(request),
        statut="success",
    )


def _csv_response(rows, columns, filename):
    """Build a semicolon-separated CSV download response."""
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _json_download_response(payload, filename):
    """Build a JSON download response for filtered exports."""
    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
