from __future__ import annotations

from html import escape
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail import send_mail
from django.utils import timezone

from api.models import Alerte, TechnicienStation


logger = logging.getLogger(__name__)
NOTIFIABLE_ALERT_STATUSES = {"active"}
CRITICAL_SEVERITIES = {"critique", "critical"}


def send_reservation_qr_email(reservation, access_payload):
    """Send the reservation QR code by email to the reservation owner."""
    if not getattr(settings, "RESERVATION_QR_EMAIL_ENABLED", True):
        return 0

    user = reservation.utilisateur
    recipient = (getattr(user, "email", "") or "").strip()
    if not recipient:
        logger.info("Reservation QR email skipped: reservation %s has no user email", reservation.id_reservation)
        return 0

    station = reservation.emplacement.station
    borne = reservation.emplacement.borne
    starts_at = timezone.localtime(reservation.date_debut).strftime("%d/%m/%Y %H:%M")
    ends_at = timezone.localtime(reservation.date_fin).strftime("%d/%m/%Y %H:%M")
    subject = f"Votre QR code de réservation {reservation.reference_code}"
    body = "\n".join(
        [
            "Votre réservation de recharge est confirmée.",
            "",
            f"Code de réservation: {reservation.reference_code}",
            f"Station: {station.nom}",
            f"Borne: {borne.nom}",
            f"Emplacement: {reservation.emplacement.numero}",
            f"Créneau: {starts_at} - {ends_at}",
            "",
            "Présentez le QR code depuis votre espace utilisateur ou ce message.",
            "Le QR code reste accepté uniquement sur le bon créneau, la bonne borne et tant que la réservation reste active.",
        ]
    )
    html = _reservation_qr_html(
        reservation,
        access_payload,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    message = EmailMultiAlternatives(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "Station <no-reply@station.local>"),
        [recipient],
    )
    message.attach_alternative(html, "text/html")
    return message.send(fail_silently=False)


def _reservation_qr_html(reservation, access_payload, *, starts_at, ends_at):
    """Build the HTML variant of the reservation QR email."""
    station = escape(reservation.emplacement.station.nom)
    borne = escape(reservation.emplacement.borne.nom)
    qr_svg = access_payload.get("qr_svg") or ""
    qr_block = qr_svg if qr_svg else "<p>QR code indisponible. Consultez votre espace utilisateur.</p>"
    return f"""<!doctype html>
<html lang="fr">
<body style="font-family:Arial,sans-serif;color:#17202e;line-height:1.5">
  <h1 style="font-size:22px">Réservation de recharge confirmée</h1>
  <p>Votre QR code d'accès est prêt.</p>
  <div style="max-width:260px;margin:16px 0;padding:12px;border:1px solid #d0d5dd;border-radius:8px">
    {qr_block}
  </div>
  <table style="border-collapse:collapse">
    <tr><td style="padding:4px 12px 4px 0;color:#667085">Code</td><td><strong>{escape(reservation.reference_code)}</strong></td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#667085">Station</td><td>{station}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#667085">Borne</td><td>{borne}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#667085">Emplacement</td><td>{reservation.emplacement.numero}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#667085">Créneau</td><td>{escape(starts_at)} - {escape(ends_at)}</td></tr>
  </table>
  <p style="color:#667085">Ce QR code est valable uniquement pour cette réservation.</p>
</body>
</html>"""


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
            "Une nouvelle alerte a été détectée sur la station.",
            "",
            f"Station: {station_label}",
            f"Borne: {borne_label}",
            f"Emplacement: {emplacement_label}",
            f"Type: {alert.type}",
            f"Sévérité: {alert.niveau_severite}",
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
