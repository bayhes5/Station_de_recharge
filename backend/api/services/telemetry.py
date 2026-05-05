from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from api.models import Alerte, Capteur, CapteurData, Device, Emplacement, Session, SessionTelemetry


SENSOR_FIELDS = {
    "temperature": ("temperature", "C"),
    "humidity": ("humidity", "%"),
    "door": ("door", "bool"),
    "cable": ("cable", "bool"),
    "state": ("state", "state"),
    "power": ("power", "W"),
}


@dataclass(frozen=True)
class TelemetryResult:
    """Summarize the records created from one MQTT telemetry payload."""

    device: Device
    capteur_count: int
    alert_count: int
    session_telemetry_created: bool


def _parse_timestamp(value: Any):
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
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_as_float(value: Any):
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value in {0, 1, "0", "1"}:
        return float(value)
    return None


def _sensor_value(sensor_type: str, value: Any):
    if sensor_type in {"door", "cable"}:
        return _bool_as_float(value)
    if sensor_type == "state":
        return None
    return _as_float(value)


def _get_device(slot_id: str) -> Device:
    try:
        return Device.objects.select_related("emplacement").get(mac_address=slot_id)
    except Device.DoesNotExist:
        emplacement = Emplacement.objects.select_related("station").first()
        if emplacement is None:
            raise ValueError("Aucun emplacement n'existe pour rattacher la telemetrie MQTT.")
        return Device.objects.create(
            emplacement=emplacement,
            type_device="ESP32",
            firmware_version="unknown",
            mac_address=slot_id,
            status="online",
            last_seen=timezone.now(),
        )


def _get_active_session(emplacement: Emplacement, session_id: str | None):
    queryset = Session.objects.filter(emplacement=emplacement, end_time__isnull=True)
    if session_id:
        session = queryset.filter(id_session=session_id).first()
        if session:
            return session
    return queryset.order_by("-start_time").first()


def _store_sensor(device: Device, sensor_type: str, unit: str, value: Any, timestamp):
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


def _create_alert_if_needed(device: Device, payload: dict[str, Any], timestamp):
    alerts = []
    state = str(payload.get("state") or "").lower()
    if state in {"error", "emergency", "fault"}:
        alerts.append(("state_error", f"Etat critique remonte par {device.mac_address}: {state}", "critique"))
    if payload.get("door") is False and state == "charging":
        alerts.append(("intrusion", "Boitier ouvert pendant une charge active.", "critique"))
    if payload.get("cable") is False and state == "charging":
        alerts.append(("cable_removed", "Cable retire pendant une charge active.", "haute"))

    temperature = _as_float(payload.get("temperature"))
    if temperature is not None and temperature >= 60:
        alerts.append(("overheat", f"Temperature elevee: {temperature:.1f} C.", "critique"))

    current = _as_float(payload.get("current"))
    if current is not None and current >= 3.0:
        alerts.append(("overcurrent", f"Surconsommation detectee: {current:.2f} A.", "haute"))

    created = []
    session = _get_active_session(device.emplacement, payload.get("session_id"))
    for alert_type, message, severity in alerts:
        created.append(
            Alerte.objects.create(
                session=session,
                type=alert_type,
                message=message,
                niveau_severite=severity,
                status="nouvelle",
                timestamp=timestamp,
            )
        )
    return created


@transaction.atomic
def ingest_slot_telemetry(slot_id: str, payload: dict[str, Any]) -> TelemetryResult:
    """Persist one ESP32 telemetry payload into operational and sensor tables."""
    if not slot_id:
        raise ValueError("slot_id est obligatoire.")

    timestamp = _parse_timestamp(payload.get("timestamp"))
    device = _get_device(slot_id)
    device.last_seen = timestamp
    device.status = str(payload.get("state") or "online")[:50]
    device.save(update_fields=["last_seen", "status"])

    capteur_records = []
    for payload_key, (sensor_type, unit) in SENSOR_FIELDS.items():
        if payload_key in payload:
            record = _store_sensor(device, sensor_type, unit, payload[payload_key], timestamp)
            if record:
                capteur_records.append(record)

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

    alerts = _create_alert_if_needed(device, payload, timestamp)
    return TelemetryResult(
        device=device,
        capteur_count=len(capteur_records),
        alert_count=len(alerts),
        session_telemetry_created=session_telemetry_created,
    )
