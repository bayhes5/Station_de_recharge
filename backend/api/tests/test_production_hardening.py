from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from django.test import override_settings
from django.utils import timezone

from api.models import (
    Alerte,
    AlertSeverity,
    AlertStatus,
    Authentification,
    Capteur,
    CapteurData,
    ChargeSessionState,
    Device,
    DeviceCommandLog,
    DeviceStatus,
    DeviceType,
    JournalSecurite,
    Reservation,
    ReservationStatus,
    SecurityLogStatus,
    Session,
    SessionTelemetry,
    TypeAuth,
)
from api.services.retention import apply_privacy_retention, prune_old_telemetry
from api.tasks import apply_privacy_retention_task, prune_old_telemetry_task


REPO_ROOT = Path(__file__).resolve().parents[3]


def _require_repo_file(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not available in this isolated backend image.")
    return path


def test_prod_compose_limits_ports_and_rotates_docker_logs():
    """Ensure the production stack exposes only edge ports and rotates JSON logs."""
    compose = yaml.safe_load(_require_repo_file(REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    allowed_published_ports = {
        "mailpit": ["127.0.0.1:8025:8025"],
        "mqtt": ["${MQTT_PUBLISHED_HOST:-127.0.0.1}:1883:1883"],
        "reverse-proxy": ["80:80", "443:443"],
    }

    for service_name, service in services.items():
        assert service.get("logging") == {
            "driver": "json-file",
            "options": {"max-size": "10m", "max-file": "5"},
        }
        if service_name in allowed_published_ports:
            assert service.get("ports") == allowed_published_ports[service_name]
        else:
            assert "ports" not in service


def test_prod_images_are_pinned_by_digest():
    """Keep production image sources immutable unless a maintainer updates them."""
    compose = yaml.safe_load(_require_repo_file(REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    image_services = ["db", "redis", "mailpit", "mqtt", "grafana", "reverse-proxy"]
    for service_name in image_services:
        image = compose["services"][service_name]["image"]
        assert "@sha256:" in image
        assert ":latest" not in image

    for relative_path in ["backend/Dockerfile", "frontend/Dockerfile", "raspberry/Dockerfile"]:
        dockerfile = _require_repo_file(REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "@sha256:" in dockerfile


def test_postgres_prod_config_enables_query_statistics_and_slow_query_logs():
    """Ensure PostgreSQL production config supports query analysis."""
    config = _require_repo_file(REPO_ROOT / "postgresql" / "prod" / "postgresql.conf").read_text(encoding="utf-8")

    assert "shared_preload_libraries = 'timescaledb,pg_stat_statements'" in config
    assert "pg_stat_statements.track = all" in config
    assert "log_min_duration_statement = 1000" in config
    assert "wal_compression = on" in config


def test_postgresql_anonymizer_migration_is_optional_and_versioned():
    """Keep PostgreSQL Anonymizer rules ready without breaking dev databases."""
    migration = _require_repo_file(
        REPO_ROOT / "backend" / "api" / "migrations" / "0027_optional_postgresql_anonymizer.py"
    ).read_text(encoding="utf-8")

    assert '_extension_available(cursor, "anon")' in migration
    assert "CREATE EXTENSION IF NOT EXISTS anon CASCADE;" in migration
    assert '"utilisateur",\n        "email"' in migration
    assert '"profil_utilisateur",\n        "telephone"' in migration
    assert '"technicien",\n        "email"' in migration
    assert "SECURITY LABEL FOR anon ON COLUMN {table_name}.{column_name}" in migration


def test_backup_and_restore_scripts_have_guardrails():
    """Ensure operational scripts are versioned with restore confirmation."""
    backup_script = _require_repo_file(REPO_ROOT / "scripts" / "backup-prod.sh").read_text(encoding="utf-8")
    restore_script = _require_repo_file(REPO_ROOT / "scripts" / "restore-prod.sh").read_text(encoding="utf-8")

    assert "pg_dump" in backup_script
    assert "--clean" in backup_script
    assert "sha256sum" in backup_script
    assert '. "$ENV_FILE"' not in backup_script
    assert '. "$ENV_FILE"' not in restore_script
    assert 'RESTORE_CONFIRM:-}" != "YES"' in restore_script
    assert "ON_ERROR_STOP=1" in restore_script
    assert "docker compose -f" in restore_script


@pytest.mark.django_db
def test_prune_old_telemetry_deletes_only_data_outside_retention_window(emplacements):
    """Apply the configured telemetry retention window without touching recent data."""
    now = timezone.now()
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device=DeviceType.ESP32,
        firmware_version="prototype",
        mac_address="aa:bb:cc:dd:ee:01",
        status=DeviceStatus.ONLINE,
    )
    capteur = Capteur.objects.create(device=device, type="temperature", unite="C")
    old_data = CapteurData.objects.create(capteur=capteur, valeur=20, timestamp=now - timedelta(days=91))
    recent_data = CapteurData.objects.create(capteur=capteur, valeur=21, timestamp=now - timedelta(days=2))

    with override_settings(TELEMETRY_RETENTION_DAYS=90):
        result = prune_old_telemetry(now=now)

    assert result.enabled is True
    assert result.deleted == 1
    assert not CapteurData.objects.filter(id_data=old_data.id_data).exists()
    assert CapteurData.objects.filter(id_data=recent_data.id_data).exists()


@pytest.mark.django_db
def test_prune_old_telemetry_task_reports_policy_result():
    """Expose retention runs through Celery Beat for production operations."""
    with override_settings(TELEMETRY_RETENTION_DAYS=0):
        result = prune_old_telemetry_task()

    assert result == {
        "enabled": False,
        "retention_days": 0,
        "deleted": 0,
        "cutoff": None,
    }


@pytest.mark.django_db
def test_apply_privacy_retention_prunes_operational_history(emplacements, user):
    """Apply the broader RGPD retention window to technical history."""
    now = timezone.now()
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device=DeviceType.ESP32,
        firmware_version="prototype",
        mac_address="aa:bb:cc:dd:ee:02",
        status=DeviceStatus.ONLINE,
    )
    capteur = Capteur.objects.create(device=device, type="temperature", unite="C")
    old_data = CapteurData.objects.create(capteur=capteur, valeur=18, timestamp=now - timedelta(days=91))
    recent_data = CapteurData.objects.create(capteur=capteur, valeur=19, timestamp=now - timedelta(days=1))
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        date_debut=now - timedelta(days=500),
        date_fin=now - timedelta(days=500, hours=-1),
        statut=ReservationStatus.COMPLETED,
    )
    session = Session.objects.create(
        reservation=reservation,
        emplacement=emplacements[0],
        start_time=now - timedelta(days=500),
        end_time=now - timedelta(days=500, hours=-1),
        charge_state=ChargeSessionState.STOPPED,
    )
    old_session_data = SessionTelemetry.objects.create(
        session=session,
        courant=1,
        tension=12,
        energie_kwh=0.1,
        timestamp=now - timedelta(days=370),
    )
    recent_session_data = SessionTelemetry.objects.create(
        session=session,
        courant=1,
        tension=12,
        energie_kwh=0.2,
        timestamp=now - timedelta(days=10),
    )
    old_command = DeviceCommandLog.objects.create(device=device, session=session, timestamp=now - timedelta(days=370))
    recent_command = DeviceCommandLog.objects.create(device=device, session=session, timestamp=now - timedelta(days=10))
    old_log = JournalSecurite.objects.create(
        utilisateur=user,
        action="old-login",
        ip="192.168.1.10",
        statut=SecurityLogStatus.SUCCESS,
        date_action=now - timedelta(days=370),
    )
    recent_log = JournalSecurite.objects.create(
        utilisateur=user,
        action="recent-login",
        ip="192.168.1.11",
        statut=SecurityLogStatus.SUCCESS,
        date_action=now - timedelta(days=10),
    )
    old_alert = Alerte.objects.create(
        session=session,
        type="overheat",
        message="Ancienne alerte resolue",
        niveau_severite=AlertSeverity.HIGH,
        status=AlertStatus.RESOLVED,
        timestamp=now - timedelta(days=370),
        first_seen=now - timedelta(days=370),
        last_seen=now - timedelta(days=370),
        resolved_at=now - timedelta(days=370),
    )
    recent_alert = Alerte.objects.create(
        session=session,
        type="overheat",
        message="Alerte recente resolue",
        niveau_severite=AlertSeverity.HIGH,
        status=AlertStatus.RESOLVED,
        timestamp=now - timedelta(days=10),
        first_seen=now - timedelta(days=10),
        last_seen=now - timedelta(days=10),
        resolved_at=now - timedelta(days=10),
    )
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    old_auth = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur="old-code",
        is_active=False,
        created_at=now - timedelta(days=100),
    )
    recent_auth = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur="recent-code",
        is_active=False,
        created_at=now - timedelta(days=10),
    )

    with override_settings(
        TELEMETRY_RETENTION_DAYS=90,
        PRIVACY_RETENTION_ENABLED=True,
        SESSION_TELEMETRY_RETENTION_DAYS=365,
        DEVICE_COMMAND_LOG_RETENTION_DAYS=365,
        SECURITY_LOG_RETENTION_DAYS=365,
        ALERT_RETENTION_DAYS=365,
        AUTH_METHOD_RETENTION_DAYS=90,
        USER_ANONYMIZATION_RETENTION_DAYS=1095,
    ):
        result = apply_privacy_retention(now=now)

    assert result.enabled is True
    assert result.deleted["capteur_data"] == 1
    assert result.deleted["session_telemetry"] == 1
    assert result.deleted["device_command_log"] == 1
    assert result.deleted["security_log"] == 1
    assert result.deleted["resolved_alert"] == 1
    assert result.deleted["auth_method"] == 1
    assert not CapteurData.objects.filter(id_data=old_data.id_data).exists()
    assert CapteurData.objects.filter(id_data=recent_data.id_data).exists()
    assert not SessionTelemetry.objects.filter(id_telemetry=old_session_data.id_telemetry).exists()
    assert SessionTelemetry.objects.filter(id_telemetry=recent_session_data.id_telemetry).exists()
    assert not DeviceCommandLog.objects.filter(id_command=old_command.id_command).exists()
    assert DeviceCommandLog.objects.filter(id_command=recent_command.id_command).exists()
    assert not JournalSecurite.objects.filter(id_log=old_log.id_log).exists()
    assert JournalSecurite.objects.filter(id_log=recent_log.id_log).exists()
    assert not Alerte.objects.filter(id_alerte=old_alert.id_alerte).exists()
    assert Alerte.objects.filter(id_alerte=recent_alert.id_alerte).exists()
    assert not Authentification.objects.filter(id_auth=old_auth.id_auth).exists()
    assert Authentification.objects.filter(id_auth=recent_auth.id_auth).exists()


def test_apply_privacy_retention_task_reports_policy_result():
    """Expose full privacy retention runs through Celery Beat."""
    with override_settings(PRIVACY_RETENTION_ENABLED=False):
        result = apply_privacy_retention_task()

    assert result == {
        "enabled": False,
        "cutoffs": {},
        "deleted": {},
        "anonymized_users": 0,
    }


def test_celery_beat_runs_telemetry_retention_policy():
    """Ensure the retention task is scheduled in production."""
    from django.conf import settings

    schedule = settings.CELERY_BEAT_SCHEDULE
    assert schedule["prune-old-telemetry"]["task"] == "api.prune_old_telemetry"
    assert schedule["apply-privacy-retention"]["task"] == "api.apply_privacy_retention"
