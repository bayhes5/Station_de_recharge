from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def _require_repo_file(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not available in this isolated backend image.")
    return path


def test_backend_dev_and_runtime_images_drop_root_privileges():
    """Ensure backend-derived containers do not run Django/Celery as root."""
    dockerfile = _require_repo_file(REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM base AS dev" in dockerfile
    assert "FROM base AS runtime" in dockerfile
    assert dockerfile.count("USER station") >= 2
    assert "adduser --system --ingroup station station" in dockerfile


def test_compose_runs_celery_beat_for_periodic_supervision_tasks():
    """Ensure the local stack includes the periodic supervision scheduler."""
    compose = yaml.safe_load(_require_repo_file(REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    celery_beat = compose["services"]["celery-beat"]

    assert celery_beat["command"] == "celery -A config beat -l info --schedule /tmp/celerybeat-schedule"
    assert celery_beat["depends_on"]["redis"]["condition"] == "service_healthy"
    assert celery_beat["depends_on"]["db"]["condition"] == "service_healthy"


def test_raspberry_image_is_built_non_root_and_keeps_state_outside_code():
    """Ensure the kiosk container is production-shaped, not pip-installed as root."""
    compose = yaml.safe_load(_require_repo_file(REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    raspberry = compose["services"]["raspberry"]
    dockerfile = _require_repo_file(REPO_ROOT / "raspberry" / "Dockerfile").read_text(encoding="utf-8")

    assert raspberry["build"]["context"] == "./raspberry"
    assert raspberry["volumes"] == ["./raspberry/app:/app:ro"]
    assert raspberry["environment"]["OFFLINE_DB_PATH"] == "/tmp/offline_cache.sqlite3"
    assert raspberry["environment"]["CHARGE_STATE_DB_PATH"] == "/tmp/charge_state.sqlite3"
    assert "ENV PYTHONDONTWRITEBYTECODE=1" in dockerfile
    assert "USER station" in dockerfile
    assert 'CMD ["python", "main.py"]' in dockerfile
