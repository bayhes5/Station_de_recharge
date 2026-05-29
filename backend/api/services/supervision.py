from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from api.models import (
    Alerte,
    AlertStatus,
    CapteurData,
    Device,
    DeviceCommandLog,
    FirmwareUpdateStatus,
)
from api.services.firmware import expected_firmware_version, firmware_update_required

DEVICE_ONLINE_GRACE_MINUTES = getattr(settings, "DEVICE_ONLINE_GRACE_MINUTES", 5)
DEVICE_STATUS_DISPLAY = {
    "online": "Disponible",
    "offline": "Hors ligne",
    "charging": "Charge en cours",
    "idle": "Disponible",
    "error": "Erreur",
    "provisioned": "Provisionné",
}
RESOLVED_ALERT_STATUSES = ["resolved", "resolue", "closed", "fermee"]
ALERT_STATUS_DISPLAY = {
    AlertStatus.NEW: "Nouvelle",
    AlertStatus.ACTIVE: "Active",
    AlertStatus.IN_PROGRESS: "Prise en charge",
    AlertStatus.RESOLVED: "Résolue",
    AlertStatus.CLOSED: "Fermée",
    AlertStatus.FERMEE: "Fermée",
    "resolved": "Résolue",
}


def device_slot_id(device):
    """Return the logical MQTT slot identifier for one device."""
    return device.slot_id or device.mac_address or str(device.id_device)


def device_is_online(device, now=None):
    """Return whether a device has sent telemetry recently enough."""
    if not device.last_seen:
        return False
    now = now or timezone.now()
    return device.last_seen >= now - timedelta(minutes=DEVICE_ONLINE_GRACE_MINUTES)


def device_status_display(device):
    """Return a supervision-friendly label for the last ESP32 state."""
    if not device.last_seen:
        return "Aucune télémétrie reçue"
    raw_status = (device.status or "").strip()
    return DEVICE_STATUS_DISPLAY.get(raw_status.lower(), raw_status or "-")


def device_last_command_display(device):
    """Return the last ESP32 command acknowledgement in a compact form."""
    parts = [
        (device.last_command_action or "").strip(),
        (device.last_command_status or "").strip(),
    ]
    label = " ".join(part for part in parts if part)
    if device.last_command_message:
        label = f"{label} - {device.last_command_message}" if label else device.last_command_message
    return label or "-"


def serialize_device_supervision(device, now=None):
    """Return one ESP32 state row for the admin supervision screen."""
    online = device_is_online(device, now=now)
    emplacement = device.emplacement
    station = emplacement.station
    borne = emplacement.borne
    return {
        "id_device": str(device.id_device),
        "slot_id": device_slot_id(device),
        "slot_label": f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}",
        "type_device": device.type_device,
        "firmware_version": device.firmware_version,
        "expected_firmware_version": device.expected_firmware_version,
        "effective_expected_firmware_version": expected_firmware_version(device),
        "firmware_update_status": device.firmware_update_status,
        "firmware_update_required": firmware_update_required(device),
        "ota_target_version": device.ota_target_version,
        "ota_requested_at": device.ota_requested_at.isoformat() if device.ota_requested_at else None,
        "ota_completed_at": device.ota_completed_at.isoformat() if device.ota_completed_at else None,
        "ota_last_error": device.ota_last_error,
        "ip_address": device.ip_address,
        "hardware_mac": device.hardware_mac,
        "status": device.status,
        "status_display": device_status_display(device),
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        "online": online,
        "health": "online" if online else "offline",
        "last_command_id": device.last_command_id,
        "last_command_action": device.last_command_action,
        "last_command_status": device.last_command_status,
        "last_command_message": device.last_command_message,
        "last_command_at": device.last_command_at.isoformat() if device.last_command_at else None,
        "last_command_display": device_last_command_display(device),
        "station_id": str(station.id_station),
        "station_nom": station.nom,
        "borne_nom": borne.nom,
        "borne_numero": borne.numero,
        "emplacement_numero": emplacement.numero,
        "emplacement_statut": emplacement.statut,
        "lock_state": emplacement.lock_state,
    }


def serialize_alert_supervision(alert):
    """Return one operational alert for the admin supervision screen."""
    session = alert.session
    data = alert.data
    device = data.capteur.device if data and data.capteur else None
    emplacement = session.emplacement if session else device.emplacement if device else None
    station = emplacement.station if emplacement else None
    borne = emplacement.borne if emplacement else None
    return {
        "id_alerte": str(alert.id_alerte),
        "type": alert.type,
        "message": alert.message,
        "niveau_severite": alert.niveau_severite,
        "status": alert.status,
        "status_display": ALERT_STATUS_DISPLAY.get(alert.status, alert.status),
        "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
        "first_seen": alert.first_seen.isoformat() if alert.first_seen else None,
        "last_seen": alert.last_seen.isoformat() if alert.last_seen else None,
        "assigned_technician": str(alert.assigned_technician_id) if alert.assigned_technician_id else None,
        "assigned_technician_nom": alert.assigned_technician.nom if alert.assigned_technician else "",
        "acknowledged_by": str(alert.acknowledged_by_id) if alert.acknowledged_by_id else None,
        "acknowledged_by_nom": alert.acknowledged_by.nom if alert.acknowledged_by else "",
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_by": str(alert.resolved_by_id) if alert.resolved_by_id else None,
        "resolved_by_nom": alert.resolved_by.nom if alert.resolved_by else "",
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolution_note": alert.resolution_note,
        "station_id": str(station.id_station) if station else None,
        "station_nom": station.nom if station else "-",
        "borne_nom": borne.nom if borne else "-",
        "borne_numero": borne.numero if borne else "-",
        "emplacement_numero": emplacement.numero if emplacement else "-",
        "session_id": str(session.id_session) if session else None,
    }


def serialize_sensor_data_supervision(sensor_data):
    """Return one recent sensor measurement for the admin supervision screen."""
    capteur = sensor_data.capteur
    device = capteur.device
    emplacement = device.emplacement if device else None
    station = emplacement.station if emplacement else None
    borne = emplacement.borne if emplacement else None
    display_value = None
    if capteur.type == "door":
        display_value = "Boîtier fermé" if sensor_data.valeur == 1 else "Boîtier ouvert"
    elif capteur.type == "cable":
        display_value = "Câble présent" if sensor_data.valeur == 1 else "Câble retiré"
    elif capteur.type == "lock":
        display_value = "Serrure verrouillée" if sensor_data.valeur == 1 else "Serrure déverrouillée"
    elif capteur.type == "intrusion":
        display_value = "Intrusion détectée" if sensor_data.valeur == 1 else "Aucune intrusion"
    return {
        "id_data": str(sensor_data.id_data),
        "type": capteur.type,
        "unite": capteur.unite,
        "valeur": sensor_data.valeur,
        "display_value": display_value,
        "timestamp": sensor_data.timestamp.isoformat() if sensor_data.timestamp else None,
        "slot_id": device_slot_id(device) if device else "-",
        "slot_label": (
            f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}"
            if emplacement and station and borne
            else "-"
        ),
        "station_id": str(station.id_station) if station else None,
        "station_nom": station.nom if station else "-",
        "borne_nom": borne.nom if borne else "-",
        "borne_numero": borne.numero if borne else "-",
        "emplacement_numero": emplacement.numero if emplacement else "-",
    }


def serialize_command_log_supervision(command):
    """Return one recent ESP32 command acknowledgement for the admin screen."""
    device = command.device
    emplacement = device.emplacement if device else None
    station = emplacement.station if emplacement else None
    borne = emplacement.borne if emplacement else None
    return {
        "id_command": str(command.id_command),
        "command_id": command.command_id,
        "action": command.action,
        "status": command.status,
        "message": command.message,
        "source": command.source,
        "timestamp": command.timestamp.isoformat() if command.timestamp else None,
        "session_id": str(command.session_id) if command.session_id else None,
        "slot_id": device_slot_id(device) if device else "-",
        "slot_label": (
            f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}"
            if emplacement and station and borne
            else "-"
        ),
        "station_id": str(station.id_station) if station else None,
        "station_nom": station.nom if station else "-",
        "borne_nom": borne.nom if borne else "-",
        "borne_numero": borne.numero if borne else "-",
        "emplacement_numero": emplacement.numero if emplacement else "-",
    }


def _normalize_station_scope(station_ids):
    """Return a stable station scope list or None for global supervision."""
    if station_ids is None:
        return None
    return [str(station_id) for station_id in station_ids]


def _alert_station_filter(station_ids):
    """Build the alert filter matching either session or sensor station context."""
    return Q(session__emplacement__station_id__in=station_ids) | Q(
        data__capteur__device__emplacement__station_id__in=station_ids
    )


def _empty_supervision_payload(station_ids):
    """Return an empty scoped payload when a technician has no active station."""
    return {
        "scope": {
            "station_ids": station_ids,
            "restricted": True,
        },
        "stats": {
            "devices_total": 0,
            "devices_online": 0,
            "devices_offline": 0,
            "active_alerts": 0,
            "critical_alerts": 0,
            "telemetry_samples_24h": 0,
        },
        "devices": [],
        "alerts": [],
        "measurements": [],
        "commands": [],
    }


def build_admin_supervision_payload(station_ids=None):
    """Build the supervision snapshot used by HTTP and WebSocket flows."""
    now = timezone.now()
    station_ids = _normalize_station_scope(station_ids)
    if station_ids is not None and not station_ids:
        return _empty_supervision_payload(station_ids)

    devices_queryset = Device.objects.select_related(
        "emplacement",
        "emplacement__station",
        "emplacement__borne",
    )
    active_alerts = Alerte.objects.exclude(status__in=RESOLVED_ALERT_STATUSES)
    recent_alerts_queryset = Alerte.objects.select_related(
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
    recent_sensor_data_queryset = CapteurData.objects.select_related(
        "capteur",
        "capteur__device",
        "capteur__device__emplacement",
        "capteur__device__emplacement__station",
        "capteur__device__emplacement__borne",
    )
    recent_commands_queryset = DeviceCommandLog.objects.select_related(
        "device",
        "device__emplacement",
        "device__emplacement__station",
        "device__emplacement__borne",
        "session",
    )
    sensor_since = now - timedelta(hours=24)
    telemetry_queryset = CapteurData.objects.filter(timestamp__gte=sensor_since)

    if station_ids is not None:
        devices_queryset = devices_queryset.filter(emplacement__station_id__in=station_ids)
        alert_scope = _alert_station_filter(station_ids)
        active_alerts = active_alerts.filter(alert_scope)
        recent_alerts_queryset = recent_alerts_queryset.filter(alert_scope)
        recent_sensor_data_queryset = recent_sensor_data_queryset.filter(
            capteur__device__emplacement__station_id__in=station_ids
        )
        recent_commands_queryset = recent_commands_queryset.filter(
            device__emplacement__station_id__in=station_ids
        )
        telemetry_queryset = telemetry_queryset.filter(
            capteur__device__emplacement__station_id__in=station_ids
        )

    devices = list(
        devices_queryset.order_by(
            "emplacement__station__nom",
            "emplacement__borne__numero",
            "emplacement__numero",
        )
    )
    recent_alerts = recent_alerts_queryset.order_by("-timestamp")[:20]
    recent_sensor_data = recent_sensor_data_queryset.order_by("-timestamp")[:30]
    recent_commands = recent_commands_queryset.order_by("-timestamp")[:30]
    alert_counts = active_alerts.aggregate(
        active_alerts=Count("id_alerte"),
        critical_alerts=Count("id_alerte", filter=Q(niveau_severite__in=["critical", "critique"])),
    )

    return {
        "scope": {
            "station_ids": station_ids or [],
            "restricted": station_ids is not None,
        },
        "stats": {
            "devices_total": len(devices),
            "devices_online": sum(1 for device in devices if device_is_online(device, now=now)),
            "devices_offline": sum(1 for device in devices if not device_is_online(device, now=now)),
            "devices_firmware_update_required": sum(
                1
                for device in devices
                if device.firmware_update_status
                in {
                    FirmwareUpdateStatus.UPDATE_REQUIRED,
                    FirmwareUpdateStatus.UPDATE_SCHEDULED,
                    FirmwareUpdateStatus.UPDATING,
                    FirmwareUpdateStatus.FAILED,
                }
            ),
            "active_alerts": alert_counts["active_alerts"],
            "critical_alerts": alert_counts["critical_alerts"],
            "telemetry_samples_24h": telemetry_queryset.count(),
        },
        "devices": [serialize_device_supervision(device, now=now) for device in devices],
        "alerts": [serialize_alert_supervision(alert) for alert in recent_alerts],
        "measurements": [serialize_sensor_data_supervision(data) for data in recent_sensor_data],
        "commands": [serialize_command_log_supervision(command) for command in recent_commands],
    }
