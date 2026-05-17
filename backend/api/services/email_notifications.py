from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from api.models import Alerte, TechnicienStation


logger = logging.getLogger(__name__)


def _alert_location(alert):
    """Resolve the station, cabinet and charging bay linked to an alert."""
    session = alert.session
    data = alert.data
    device = data.capteur.device if data and data.capteur else None
    emplacement = session.emplacement if session else device.emplacement if device else None
    station = emplacement.station if emplacement else None
    borne = emplacement.borne if emplacement else None
    return station, borne, emplacement


def _technician_recipients(station):
    """Return active technician email recipients for one station."""
    if station is None:
        return []
    recipients = (
        TechnicienStation.objects.filter(station=station, is_active=True)
        .exclude(technicien__email="")
        .values_list("technicien__email", flat=True)
        .distinct()
    )
    return sorted({email.strip() for email in recipients if email and email.strip()})


def _alert_email_content(alert):
    """Build the subject and body sent to station technicians."""
    station, borne, emplacement = _alert_location(alert)
    station_label = station.nom if station else "Station inconnue"
    borne_label = borne.nom if borne else "Borne inconnue"
    emplacement_label = f"Emplacement {emplacement.numero}" if emplacement else "Emplacement inconnu"
    subject = f"[Station] Alerte {alert.niveau_severite} - {station_label}"
    body = "\n".join(
        [
            "Une nouvelle alerte a ete detectee sur la station.",
            "",
            f"Station: {station_label}",
            f"Borne: {borne_label}",
            f"Emplacement: {emplacement_label}",
            f"Type: {alert.type}",
            f"Severite: {alert.niveau_severite}",
            f"Statut: {alert.status}",
            f"Message: {alert.message}",
            f"Date: {alert.timestamp.isoformat() if alert.timestamp else '-'}",
            "",
            "Consultez le dashboard de supervision pour traiter l'incident.",
        ]
    )
    return subject, body


def notify_technicians_for_alert(alert_id):
    """Send one operational alert notification to assigned technicians."""
    if not getattr(settings, "ALERT_EMAIL_NOTIFICATIONS_ENABLED", True):
        return 0

    try:
        alert = (
            Alerte.objects.select_related(
                "session__emplacement__station",
                "session__emplacement__borne",
                "data__capteur__device__emplacement__station",
                "data__capteur__device__emplacement__borne",
            )
            .get(id_alerte=alert_id)
        )
    except Alerte.DoesNotExist:
        logger.warning("Alert email skipped: alert %s no longer exists", alert_id)
        return 0

    station, _borne, _emplacement = _alert_location(alert)
    recipients = _technician_recipients(station)
    if not recipients:
        logger.info("Alert email skipped: no technician assigned to alert %s", alert_id)
        return 0

    subject, body = _alert_email_content(alert)
    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "Station <no-reply@station.local>"),
        recipients,
        fail_silently=False,
    )
    logger.info("Alert email sent alert=%s recipients=%s", alert_id, len(recipients))
    return len(recipients)
