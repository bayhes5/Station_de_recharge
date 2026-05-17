from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from api.models import Alerte, CapteurData, Device, DeviceCommandLog

DEVICE_ONLINE_GRACE_MINUTES = getattr(settings, "DEVICE_ONLINE_GRACE_MINUTES", 5)
DEVICE_STATUS_DISPLAY = {
    "online": "Disponible",
    "offline": "Hors ligne",
    "charging": "Charge en cours",
    "idle": "Disponible",
    "error": "Erreur",
    "provisioned": "Provisionné",
}
OPEN_ALERT_STATUSES = ["resolved", "resolue", "closed", "fermee"]


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
        "slot_id": device.mac_address or str(device.id_device),
        "slot_label": f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}",
        "type_device": device.type_device,
        "firmware_version": device.firmware_version,
        "ip_address": device.ip_address,
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
        "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
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
    return {
        "id_data": str(sensor_data.id_data),
        "type": capteur.type,
        "unite": capteur.unite,
        "valeur": sensor_data.valeur,
        "display_value": display_value,
        "timestamp": sensor_data.timestamp.isoformat() if sensor_data.timestamp else None,
        "slot_id": device.mac_address if device else "-",
        "slot_label": (
            f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}"
            if emplacement and station and borne
            else "-"
        ),
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
        "slot_id": device.mac_address if device else "-",
        "slot_label": (
            f"{station.nom} - {borne.nom} - emplacement {emplacement.numero}"
            if emplacement and station and borne
            else "-"
        ),
        "station_nom": station.nom if station else "-",
        "borne_nom": borne.nom if borne else "-",
        "borne_numero": borne.numero if borne else "-",
        "emplacement_numero": emplacement.numero if emplacement else "-",
    }


def build_admin_supervision_payload():
    """Build the complete admin supervision snapshot used by HTTP and WebSocket flows."""
    now = timezone.now()
    devices = list(
        Device.objects.select_related(
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
        ).order_by("emplacement__station__nom", "emplacement__borne__numero", "emplacement__numero")
    )
    active_alerts = Alerte.objects.exclude(status__in=OPEN_ALERT_STATUSES)
    recent_alerts = (
        Alerte.objects.select_related(
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
        .order_by("-timestamp")[:20]
    )
    recent_sensor_data = (
        CapteurData.objects.select_related(
            "capteur",
            "capteur__device",
            "capteur__device__emplacement",
            "capteur__device__emplacement__station",
            "capteur__device__emplacement__borne",
        )
        .order_by("-timestamp")[:30]
    )
    recent_commands = (
        DeviceCommandLog.objects.select_related(
            "device",
            "device__emplacement",
            "device__emplacement__station",
            "device__emplacement__borne",
            "session",
        )
        .order_by("-timestamp")[:30]
    )
    sensor_since = now - timedelta(hours=24)

    return {
        "stats": {
            "devices_total": len(devices),
            "devices_online": sum(1 for device in devices if device_is_online(device, now=now)),
            "devices_offline": sum(1 for device in devices if not device_is_online(device, now=now)),
            "active_alerts": active_alerts.count(),
            "critical_alerts": active_alerts.filter(niveau_severite__in=["critical", "critique"]).count(),
            "telemetry_samples_24h": CapteurData.objects.filter(timestamp__gte=sensor_since).count(),
        },
        "devices": [serialize_device_supervision(device, now=now) for device in devices],
        "alerts": [serialize_alert_supervision(alert) for alert in recent_alerts],
        "measurements": [serialize_sensor_data_supervision(data) for data in recent_sensor_data],
        "commands": [serialize_command_log_supervision(command) for command in recent_commands],
    }
