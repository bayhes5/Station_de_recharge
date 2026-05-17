from datetime import timedelta
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from api.models import Alerte, Reservation, Session, SessionTelemetry, Technicien, TechnicienStation
from api.services.operational_alerts import scan_session_telemetry_gaps


def create_active_session(user, emplacement, *, start_delta=timedelta(minutes=5)):
    """Create one active reservation and charging session for alert tests."""
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacement,
        reference_code=f"STL{timezone.now().strftime('%H%M%S')}{emplacement.numero}",
        auth_choice="qr",
        date_debut=timezone.now() - start_delta,
        date_fin=timezone.now() + timedelta(minutes=30),
        statut="active",
    )
    return Session.objects.create(
        reservation=reservation,
        emplacement=emplacement,
        start_time=timezone.now() - start_delta,
    )


@pytest.mark.django_db
@override_settings(SESSION_TELEMETRY_STALE_MINUTES=2)
def test_scan_session_telemetry_gaps_creates_alert_for_stale_active_session(user, emplacements):
    """Raise a backend alert when an active session has no recent telemetry."""
    session = create_active_session(user, emplacements[0])

    result = scan_session_telemetry_gaps()

    assert result.created == 1
    assert result.updated == 0
    alert = Alerte.objects.get(type="session_without_telemetry")
    assert alert.session == session
    assert alert.status == "nouvelle"
    assert alert.niveau_severite == "haute"
    assert "Station Centre" in alert.message
    assert "Borne 1" in alert.message
    assert "emplacement 1" in alert.message


@pytest.mark.django_db
@override_settings(SESSION_TELEMETRY_STALE_MINUTES=2)
def test_scan_session_telemetry_gaps_ignores_session_with_recent_telemetry(user, emplacements):
    """Keep active sessions silent when session telemetry is fresh."""
    session = create_active_session(user, emplacements[0])
    SessionTelemetry.objects.create(
        session=session,
        courant=1.2,
        tension=41.5,
        energie_kwh=0.03,
        timestamp=timezone.now() - timedelta(seconds=30),
    )

    result = scan_session_telemetry_gaps()

    assert result.created == 0
    assert Alerte.objects.filter(type="session_without_telemetry").count() == 0


@pytest.mark.django_db
@override_settings(SESSION_TELEMETRY_STALE_MINUTES=2)
def test_scan_session_telemetry_gaps_resolves_when_telemetry_returns(user, emplacements):
    """Resolve the session telemetry alert as soon as a recent sample exists."""
    session = create_active_session(user, emplacements[0])
    first_result = scan_session_telemetry_gaps()
    assert first_result.created == 1

    SessionTelemetry.objects.create(
        session=session,
        courant=1.2,
        tension=41.5,
        energie_kwh=0.03,
        timestamp=timezone.now(),
    )
    second_result = scan_session_telemetry_gaps()

    assert second_result.resolved == 1
    alert = Alerte.objects.get(type="session_without_telemetry")
    assert alert.status == "resolue"


@pytest.mark.django_db
@override_settings(SESSION_TELEMETRY_STALE_MINUTES=2)
def test_check_session_telemetry_health_command_reports_counts(user, emplacements):
    """Expose the scan as a management command for cron or container jobs."""
    create_active_session(user, emplacements[0])
    output = StringIO()

    call_command("check_session_telemetry_health", stdout=output)

    assert "created=1" in output.getvalue()
    assert Alerte.objects.filter(type="session_without_telemetry").count() == 1


@pytest.mark.django_db
@override_settings(
    SESSION_TELEMETRY_STALE_MINUTES=2,
    ALERT_NOTIFICATION_MIN_AGE_SECONDS=60,
    ALERT_TECHNICIAN_EMAIL_TYPES=["session_without_telemetry"],
)
def test_session_telemetry_gap_notifies_assigned_technician_after_policy_delay(
    user,
    emplacements,
    django_capture_on_commit_callbacks,
):
    """Notify assigned technicians only after the alert persists long enough."""
    session = create_active_session(user, emplacements[0])
    technician = Technicien.objects.create(
        nom="Technicien Centre",
        email="tech-centre@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technician, station=session.emplacement.station)
    now = timezone.now()

    with django_capture_on_commit_callbacks(execute=True):
        first_result = scan_session_telemetry_gaps(now=now - timedelta(minutes=2))

    assert first_result.created == 1
    assert mail.outbox == []

    with django_capture_on_commit_callbacks(execute=True):
        second_result = scan_session_telemetry_gaps(now=now)

    assert second_result.updated == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["tech-centre@example.com"]
    assert "session_without_telemetry" in mail.outbox[0].body
