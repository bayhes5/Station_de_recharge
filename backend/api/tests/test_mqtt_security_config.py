from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
MOSQUITTO_CONFIG = REPO_ROOT / "mosquitto" / "config"


def _read_config(name: str) -> str:
    """Read one Mosquitto configuration file from the repository root."""
    path = MOSQUITTO_CONFIG / name
    if not path.exists():
        pytest.skip(f"{path} is not available in this isolated backend image.")
    return path.read_text(encoding="utf-8")


def _user_acl_block(acl: str, username: str) -> str:
    """Return the ACL lines belonging to one Mosquitto user section."""
    marker = f"user {username}"
    lines = acl.splitlines()
    start = lines.index(marker)
    block = []
    for line in lines[start:]:
        if block and line.startswith("user "):
            break
        block.append(line)
    return "\n".join(block)


def test_secure_mosquitto_config_requires_authentication():
    """Ensure the production Mosquitto example enables password and ACL checks."""
    config = _read_config("mosquitto.secure.conf")

    assert "allow_anonymous false" in config
    assert "password_file /mosquitto/config/passwords" in config
    assert "acl_file /mosquitto/config/acl" in config


def test_prod_compose_uses_secure_mosquitto_config_and_scoped_raspberry_account():
    """Ensure production cannot accidentally start the open development broker."""
    compose_path = REPO_ROOT / "docker-compose.prod.yml"
    if not compose_path.exists():
        pytest.skip(f"{compose_path} is not available in this isolated backend image.")
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    mqtt_volumes = compose["services"]["mqtt"]["volumes"]
    assert "./mosquitto/config/mosquitto.secure.conf:/mosquitto/config/mosquitto.conf:ro" in mqtt_volumes
    assert "./mosquitto/config/acl:/mosquitto/config/acl:ro" in mqtt_volumes
    assert "./mosquitto/config/passwords:/mosquitto/config/passwords:ro" in mqtt_volumes
    assert "./mosquitto/config:/mosquitto/config:ro" not in mqtt_volumes

    raspberry_env = compose["services"]["raspberry"]["environment"]
    assert raspberry_env["MQTT_ACK_REQUIRED"] == "${MQTT_ACK_REQUIRED:-true}"
    assert raspberry_env["MQTT_USERNAME"] == "${MQTT_RASPBERRY_USERNAME:?Set MQTT_RASPBERRY_USERNAME}"
    assert raspberry_env["MQTT_PASSWORD"] == "${MQTT_RASPBERRY_PASSWORD:?Set MQTT_RASPBERRY_PASSWORD}"


def test_mosquitto_acl_scopes_structured_esp32_accounts_to_one_slot():
    """Ensure structured ESP32 demo accounts cannot publish on another slot."""
    acl = _read_config("acl")
    slot1_acl = _user_acl_block(acl, "esp32_station_demo_borne_1_slot1")

    assert "user esp32_station_demo_borne_1_slot1" in acl
    assert "topic read station/station-demo/borne-1/slot1/cmd" in slot1_acl
    assert "topic write station/station-demo/borne-1/slot1/telemetry" in slot1_acl
    assert "topic write station/station-demo/borne-1/slot1/status" in slot1_acl
    assert "topic write station/station-demo/borne-1/slot1/ack" in slot1_acl
    assert "topic write station/station-demo/borne-1/slot2/status" not in slot1_acl
