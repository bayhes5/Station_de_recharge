from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from django.test import override_settings
from django.utils import timezone

from api.models import Capteur, CapteurData, Device, DeviceStatus, DeviceType
from api.services.retention import prune_old_telemetry
from api.tasks import prune_old_telemetry_task


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


def test_celery_beat_runs_telemetry_retention_policy():
    """Ensure the retention task is scheduled in production."""
    from django.conf import settings

    schedule = settings.CELERY_BEAT_SCHEDULE
    assert schedule["prune-old-telemetry"]["task"] == "api.prune_old_telemetry"
