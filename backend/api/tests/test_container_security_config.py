from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_backend_dev_and_runtime_images_drop_root_privileges():
    """Ensure backend-derived containers do not run Django/Celery as root."""
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM base AS dev" in dockerfile
    assert "FROM base AS runtime" in dockerfile
    assert dockerfile.count("USER station") >= 2
    assert "adduser --system --ingroup station station" in dockerfile


def test_compose_runs_celery_beat_for_periodic_supervision_tasks():
    """Ensure the local stack includes the periodic supervision scheduler."""
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    celery_beat = compose["services"]["celery-beat"]

    assert celery_beat["command"] == "celery -A config beat -l info --schedule /tmp/celerybeat-schedule"
    assert celery_beat["depends_on"]["redis"]["condition"] == "service_healthy"
    assert celery_beat["depends_on"]["db"]["condition"] == "service_healthy"
