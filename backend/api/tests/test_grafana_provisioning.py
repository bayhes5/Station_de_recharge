from pathlib import Path

import json
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
ALERT_RULES_PATH = REPO_ROOT / "grafana" / "provisioning" / "alerting" / "station-alerts.yml"
DASHBOARDS_PATH = REPO_ROOT / "grafana" / "dashboards"


def test_grafana_alert_rules_are_provisioned_for_production_supervision():
    """Ensure Grafana production alert rules stay versioned with the project."""
    if not ALERT_RULES_PATH.exists():
        pytest.skip(f"{ALERT_RULES_PATH} is not available in this isolated backend image.")
    config = yaml.safe_load(ALERT_RULES_PATH.read_text(encoding="utf-8"))

    assert config["apiVersion"] == 1
    groups = config["groups"]
    assert len(groups) == 1
    rules = groups[0]["rules"]
    rule_uids = {rule["uid"] for rule in rules}

    assert {
        "station_esp32_offline",
        "station_temperature_high",
        "station_current_abnormal",
        "station_charge_without_session",
        "station_session_without_telemetry",
    }.issubset(rule_uids)
    assert all(rule["condition"] == "B" for rule in rules)
    assert all(rule["data"][0]["datasourceUid"] == "station-timescaledb" for rule in rules)
    assert all(rule["data"][1]["datasourceUid"] == "__expr__" for rule in rules)


def test_grafana_session_detail_dashboard_is_provisioned():
    """Ensure the session-level Grafana dashboard stays versioned."""
    dashboard_path = DASHBOARDS_PATH / "session-detail.json"
    if not dashboard_path.exists():
        pytest.skip(f"{dashboard_path} is not available in this isolated backend image.")

    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert dashboard["uid"] == "session-detail"
    assert dashboard["title"] == "Session - Détail charge"

    variables = {variable["name"]: variable for variable in dashboard["templating"]["list"]}
    assert "session" in variables
    assert "charging_session" in variables["session"]["query"]

    raw_queries = [
        target.get("rawSql", "")
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    ]
    assert any("session_telemetry" in query for query in raw_queries)
    assert any("device_command_log" in query for query in raw_queries)
    assert any("alerte" in query for query in raw_queries)
