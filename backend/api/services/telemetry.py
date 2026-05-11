from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from api.models import (
    Alerte,
    Capteur,
    CapteurData,
    Device,
    DeviceStatus,
    Emplacement,
    Session,
    SessionTelemetry,
)


SENSOR_FIELDS = {
    "temperature": ("temperature", "C"),
    "humidity": ("humidity", "%"),
    "door": ("door", "bool"),
    "cable": ("cable", "bool"),
    "state": ("state", "state"),
    "current": ("current", "A"),
    "voltage": ("voltage", "V"),
    "power": ("power", "W"),
}

RESOLVED_ALERT_STATUSES = ["resolved", "resolue", "closed", "fermee"]
DEVICE_STATUS_ALIASES = {
    "available": DeviceStatus.ONLINE,
    "ready": DeviceStatus.ONLINE,
    "running": DeviceStatus.CHARGING,
    "emergency": DeviceStatus.ERROR,
    "fault": DeviceStatus.ERROR,
}


@dataclass(frozen=True)
class TelemetryResult:
    """Summarize the records created from one MQTT telemetry payload."""

    device: Device
    capteur_count: int
    alert_count: int
    session_telemetry_created: bool


def _parse_timestamp(value: Any):
    """Return an aware timestamp from an MQTT value or the current time."""
    if not value:
        return timezone.now()
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return timezone.now()
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    return timezone.now()


def _as_float(value: Any):
    """Convert telemetry numeric values to floats when possible."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_as_float(value: Any):
    """Convert boolean-like sensor values to numeric storage values."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value in {0, 1, "0", "1"}:
        return float(value)
    return None


def _device_status(value: Any) -> str:
    """Return a storage-safe ESP32 business state."""
    normalized = str(value or DeviceStatus.ONLINE).strip().lower()
    aliased = DEVICE_STATUS_ALIASES.get(normalized, normalized)
    return aliased if aliased in DeviceStatus.values else DeviceStatus.ERROR


def _sensor_value(sensor_type: str, value: Any):
    """Normalize one sensor value before creating a CapteurData record."""
    if sensor_type in {"door", "cable"}:
        return _bool_as_float(value)
    if sensor_type == "state":
        return None
    return _as_float(value)


def _slot_number(slot_id: str) -> int | None:
    """Extract the numeric bay number from a slot identifier."""
    match = re.search(r"(\d+)$", slot_id)
    return int(match.group(1)) if match else None


def _get_device(slot_id: str) -> Device:
    """Return the device mapped to the slot, creating it on first telemetry."""
    try:
        return Device.objects.select_related("emplacement").get(mac_address=slot_id)
    except Device.DoesNotExist:
        slot_number = _slot_number(slot_id)
        emplacement_query = Emplacement.objects.select_related("station").order_by(
            "station__nom",
            "numero",
        )
        if slot_number is not None:
            emplacement = emplacement_query.filter(numero=slot_number).first()
        else:
            emplacement = emplacement_query.first()
        if emplacement is None:
            raise ValueError("Aucun emplacement n'existe pour rattacher la telemetrie MQTT.")
        device = getattr(emplacement, "device", None)
        if device is not None:
            device.mac_address = slot_id
            device.last_seen = timezone.now()
            device.save(update_fields=["mac_address", "last_seen"])
            return device
        return Device.objects.create(
            emplacement=emplacement,
            type_device="ESP32",
            firmware_version="unknown",
            mac_address=slot_id,
            status="online",
            last_seen=timezone.now(),
        )


def _get_active_session(emplacement: Emplacement, session_id: str | None):
    """Find the current charging session for an emplacement."""
    queryset = Session.objects.filter(emplacement=emplacement, end_time__isnull=True)
    if session_id:
        try:
            session_uuid = UUID(str(session_id))
        except ValueError:
            session_uuid = None
        session = queryset.filter(id_session=session_uuid).first() if session_uuid else None
        if session:
            return session
    return queryset.order_by("-start_time").first()


def _store_sensor(device: Device, sensor_type: str, unit: str, value: Any, timestamp):
    """Store one numeric sensor sample for a device."""
    numeric_value = _sensor_value(sensor_type, value)
    if numeric_value is None:
        return None
    capteur, _created = Capteur.objects.get_or_create(
        device=device,
        type=sensor_type,
        defaults={"unite": unit},
    )
    if capteur.unite != unit:
        capteur.unite = unit
        capteur.save(update_fields=["unite"])
    return CapteurData.objects.create(capteur=capteur, valeur=numeric_value, timestamp=timestamp)


def _open_alerts_for_device(device: Device, alert_type: str):
    """Return unresolved alerts for the current device and alert type."""
    queryset = Alerte.objects.filter(type=alert_type).exclude(status__in=RESOLVED_ALERT_STATUSES)
    if alert_type == "state_error":
        return queryset.filter(Q(session__emplacement=device.emplacement) | Q(message__contains=device.mac_address))
    return queryset.filter(Q(data__capteur__device=device) | Q(session__emplacement=device.emplacement))


def _upsert_active_alert(
    device: Device,
    alert_type: str,
    message: str,
    severity: str,
    sensor_type: str | None,
    timestamp,
    session,
    sensor_records: dict[str, CapteurData],
):
    """Create a new alert or mark an existing one as still active."""
    existing = _open_alerts_for_device(device, alert_type).order_by("-timestamp").first()
    data = sensor_records.get(sensor_type) if sensor_type else None
    if existing:
        existing.message = message
        existing.niveau_severite = severity
        existing.timestamp = timestamp
        existing.status = "active"
        if data:
            existing.data = data
        if session:
            existing.session = session
        existing.save(update_fields=["message", "niveau_severite", "timestamp", "status", "data", "session"])
        return existing, False
    return (
        Alerte.objects.create(
            data=data,
            session=session,
            type=alert_type,
            message=message,
            niveau_severite=severity,
            status="nouvelle",
            timestamp=timestamp,
        ),
        True,
    )


def _resolve_alerts_for_device(device: Device, alert_type: str, timestamp):
    """Mark unresolved alerts as resolved when telemetry returns to normal."""
    return _open_alerts_for_device(device, alert_type).update(status="resolue", timestamp=timestamp)


def _alert_resolution_candidates(payload: dict[str, Any]):
    """Return alert types that can be resolved from this telemetry payload."""
    state = str(payload.get("state") or "").lower()
    candidates = []
    if "state" in payload and state not in {"error", "emergency", "fault"}:
        candidates.append("state_error")
    if "door" in payload and (payload.get("door") is not False or state != "charging"):
        candidates.append("intrusion")
    if "cable" in payload and (payload.get("cable") is not False or state != "charging"):
        candidates.append("cable_removed")
    temperature = _as_float(payload.get("temperature"))
    if temperature is not None and temperature < 60:
        candidates.append("overheat")
    current = _as_float(payload.get("current"))
    if current is not None and current < 3.0:
        candidates.append("overcurrent")
    return candidates


def _create_alert_if_needed(device: Device, payload: dict[str, Any], timestamp, sensor_records: dict[str, CapteurData]):
    """Create, update or resolve security alerts from critical telemetry states."""
    triggered_alerts = []
    state = str(payload.get("state") or "").lower()
    if state in {"error", "emergency", "fault"}:
        triggered_alerts.append(("state_error", f"Etat critique remonte par {device.mac_address}: {state}", "critique", None))
    if payload.get("door") is False and state == "charging":
        triggered_alerts.append(("intrusion", "Boitier ouvert pendant une charge active.", "critique", "door"))
    if payload.get("cable") is False and state == "charging":
        triggered_alerts.append(("cable_removed", "Cable retire pendant une charge active.", "haute", "cable"))

    temperature = _as_float(payload.get("temperature"))
    if temperature is not None and temperature >= 60:
        triggered_alerts.append(("overheat", f"Temperature elevee: {temperature:.1f} C.", "critique", "temperature"))

    current = _as_float(payload.get("current"))
    if current is not None and current >= 3.0:
        triggered_alerts.append(("overcurrent", f"Surconsommation detectee: {current:.2f} A.", "haute", "current"))

    created = []
    session = _get_active_session(device.emplacement, payload.get("session_id"))
    triggered_types = {alert_type for alert_type, _message, _severity, _sensor_type in triggered_alerts}
    for alert_type in _alert_resolution_candidates(payload):
        if alert_type not in triggered_types:
            _resolve_alerts_for_device(device, alert_type, timestamp)

    for alert_type, message, severity, sensor_type in triggered_alerts:
        alert, was_created = _upsert_active_alert(
            device,
            alert_type,
            message,
            severity,
            sensor_type,
            timestamp,
            session,
            sensor_records,
        )
        if was_created:
            created.append(alert)
    return created


@transaction.atomic
def ingest_slot_telemetry(slot_id: str, payload: dict[str, Any]) -> TelemetryResult:
    """Persist one ESP32 telemetry payload into operational and sensor tables."""
    if not slot_id:
        raise ValueError("slot_id est obligatoire.")

    timestamp = _parse_timestamp(payload.get("timestamp"))
    device = _get_device(slot_id)
    device.last_seen = timestamp
    device.status = _device_status(payload.get("state"))
    device.save(update_fields=["last_seen", "status"])

    capteur_records = []
    sensor_records = {}
    for payload_key, (sensor_type, unit) in SENSOR_FIELDS.items():
        if payload_key in payload:
            record = _store_sensor(device, sensor_type, unit, payload[payload_key], timestamp)
            if record:
                capteur_records.append(record)
                sensor_records[sensor_type] = record

    session_telemetry_created = False
    current = _as_float(payload.get("current"))
    voltage = _as_float(payload.get("voltage"))
    energy = _as_float(payload.get("energy_kwh"))
    session = _get_active_session(device.emplacement, payload.get("session_id"))
    if session and current is not None and voltage is not None:
        SessionTelemetry.objects.create(
            session=session,
            courant=current,
            tension=voltage,
            energie_kwh=energy or 0.0,
            timestamp=timestamp,
        )
        session_telemetry_created = True

    alerts = _create_alert_if_needed(device, payload, timestamp, sensor_records)
    return TelemetryResult(
        device=device,
        capteur_count=len(capteur_records),
        alert_count=len(alerts),
        session_telemetry_created=session_telemetry_created,
    )
