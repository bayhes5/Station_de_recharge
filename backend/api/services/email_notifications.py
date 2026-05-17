from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from api.models import Alerte, TechnicienStation


logger = logging.getLogger(__name__)
NOTIFIABLE_ALERT_STATUSES = {"active"}
CRITICAL_SEVERITIES = {"critique", "critical"}


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


def _technician_email_alert_types():
    """Return alert types that should be escalated to technicians by email."""
    configured = getattr(settings, "ALERT_TECHNICIAN_EMAIL_TYPES", [])
    return {str(alert_type).strip() for alert_type in configured if str(alert_type).strip()}


def _notification_delay_seconds(alert):
    """Return the persistence delay required before notifying technicians."""
    if str(alert.niveau_severite).lower() in CRITICAL_SEVERITIES:
        return getattr(settings, "ALERT_CRITICAL_NOTIFICATION_MIN_AGE_SECONDS", 60)
    return getattr(settings, "ALERT_NOTIFICATION_MIN_AGE_SECONDS", 120)


def _renotify_cooldown_seconds():
    """Return the minimum delay between two notifications for the same alert."""
    return getattr(settings, "ALERT_RENOTIFY_COOLDOWN_SECONDS", 1800)


def alert_is_ready_for_notification(alert, now=None):
    """Return whether an alert has persisted long enough to notify technicians."""
    if not getattr(settings, "ALERT_EMAIL_NOTIFICATIONS_ENABLED", True):
        return False
    if alert.type not in _technician_email_alert_types():
        return False
    if alert.status not in NOTIFIABLE_ALERT_STATUSES:
        return False

    now = now or timezone.now()
    first_seen = alert.first_seen or alert.timestamp
    if (now - first_seen).total_seconds() < _notification_delay_seconds(alert):
        return False

    if alert.notified_at:
        cooldown = _renotify_cooldown_seconds()
        if cooldown > 0 and (now - alert.notified_at).total_seconds() < cooldown:
            return False
    return True


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


def notify_technicians_for_alert(alert_id, *, force=False):
    """Send one operational alert notification to assigned technicians."""
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

    if not force and not alert_is_ready_for_notification(alert):
        logger.debug("Alert email skipped: alert %s does not match notification policy", alert_id)
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
    alert.notified_at = timezone.now()
    alert.notification_count += 1
    alert.save(update_fields=["notified_at", "notification_count"])
    logger.info("Alert email sent alert=%s recipients=%s", alert_id, len(recipients))
    return len(recipients)


def notify_pending_alerts():
    """Notify all active alerts that currently match the notification policy."""
    alert_ids = (
        Alerte.objects.filter(status__in=NOTIFIABLE_ALERT_STATUSES)
        .exclude(type="firmware_outdated")
        .values_list("id_alerte", flat=True)
    )
    sent_count = 0
    alert_count = 0
    for alert_id in alert_ids:
        recipient_count = notify_technicians_for_alert(alert_id)
        if recipient_count:
            sent_count += recipient_count
            alert_count += 1
    return {"alerts_notified": alert_count, "emails_sent": sent_count}
