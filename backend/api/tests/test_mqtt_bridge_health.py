import time
import uuid
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@pytest.fixture
def heartbeat_file(request):
    state_dir = Path(__file__).resolve().parent / ".health_tmp"
    state_dir.mkdir(exist_ok=True)
    path = state_dir / f"{uuid.uuid4().hex}.heartbeat"

    def cleanup():
        path.unlink(missing_ok=True)
        try:
            state_dir.rmdir()
        except OSError:
            # Another heartbeat fixture may still be using the shared temp dir.
            pass

    request.addfinalizer(cleanup)
    return path


def test_check_mqtt_bridge_health_accepts_fresh_heartbeat(heartbeat_file):
    heartbeat_file.write_text(str(time.time()), encoding="utf-8")

    with override_settings(
        MQTT_BRIDGE_HEARTBEAT_FILE=str(heartbeat_file),
        MQTT_BRIDGE_HEARTBEAT_MAX_AGE_SECONDS=30,
    ):
        call_command("check_mqtt_bridge_health")


def test_check_mqtt_bridge_health_rejects_missing_heartbeat(heartbeat_file):
    with override_settings(
        MQTT_BRIDGE_HEARTBEAT_FILE=str(heartbeat_file),
        MQTT_BRIDGE_HEARTBEAT_MAX_AGE_SECONDS=30,
    ):
        with pytest.raises(CommandError, match="absent"):
            call_command("check_mqtt_bridge_health")


def test_check_mqtt_bridge_health_rejects_stale_heartbeat(heartbeat_file):
    heartbeat_file.write_text(str(time.time() - 60), encoding="utf-8")

    with override_settings(
        MQTT_BRIDGE_HEARTBEAT_FILE=str(heartbeat_file),
        MQTT_BRIDGE_HEARTBEAT_MAX_AGE_SECONDS=10,
    ):
        with pytest.raises(CommandError, match="trop ancien"):
            call_command("check_mqtt_bridge_health")
