import json

import pytest

from api.models import Alerte, CapteurData, Device
from api.tasks import process_mqtt_message


@pytest.mark.django_db
def test_process_mqtt_message_stores_sensor_data(emplacements):
    """Store MQTT telemetry as sensor samples for the matching ESP32 device."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps(
            {
                "state": "charging",
                "temperature": 31.5,
                "humidity": 44,
                "current": 1.2,
                "voltage": 41.5,
                "door": True,
                "cable": True,
            }
        ),
    )

    assert result["slot_id"] == "slot1"
    assert result["capteur_count"] == 6
    assert CapteurData.objects.count() == 6
    assert set(CapteurData.objects.values_list("capteur__type", flat=True)) == {
        "temperature",
        "humidity",
        "current",
        "voltage",
        "door",
        "cable",
    }
    assert Device.objects.get(mac_address="slot1").status == "charging"


@pytest.mark.django_db
def test_process_mqtt_message_reuses_existing_blank_demo_device(emplacements):
    """Attach slot telemetry to the existing demo device for the bay number."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="",
        status="online",
    )

    result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps({"state": "charging", "temperature": 30, "door": True, "cable": True}),
    )

    assert result["slot_id"] == "slot1"
    assert Device.objects.count() == 1
    assert Device.objects.get(emplacement=emplacements[0]).mac_address == "slot1"
    assert CapteurData.objects.count() == 3


@pytest.mark.django_db
def test_process_mqtt_message_ignores_non_uuid_session_id(emplacements):
    """Store sensor samples even when simulated telemetry uses a non-UUID session id."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps(
            {
                "session_id": "simulation",
                "state": "charging",
                "temperature": 30,
                "door": True,
                "cable": True,
            }
        ),
    )

    assert result["capteur_count"] == 3
    assert CapteurData.objects.count() == 3


@pytest.mark.django_db
def test_process_mqtt_message_creates_alert_for_open_door(emplacements):
    """Raise an alert when a charging slot reports an open enclosure."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps({"state": "charging", "door": False, "cable": True}),
    )

    assert result["alert_count"] == 1
    assert Alerte.objects.get().status == "nouvelle"


@pytest.mark.django_db
def test_process_mqtt_message_updates_and_resolves_existing_alert(emplacements):
    """Keep one alert per active anomaly and resolve it when telemetry normalizes."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    first_result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps({"state": "charging", "door": False, "cable": True}),
    )
    second_result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps({"state": "charging", "door": False, "cable": True}),
    )

    assert first_result["alert_count"] == 1
    assert second_result["alert_count"] == 0
    assert Alerte.objects.count() == 1
    alert = Alerte.objects.get(type="intrusion")
    assert alert.status == "active"

    resolved_result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps({"state": "charging", "door": True, "cable": True}),
    )

    assert resolved_result["alert_count"] == 0
    alert.refresh_from_db()
    assert alert.status == "resolue"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "alert_type"),
    [
        ({"state": "charging", "door": True, "cable": False}, "cable_removed"),
        ({"state": "charging", "door": True, "cable": True, "temperature": 60}, "overheat"),
        ({"state": "charging", "door": True, "cable": True, "current": 3.0}, "overcurrent"),
        ({"state": "error", "door": True, "cable": True}, "state_error"),
    ],
)
def test_process_mqtt_message_creates_expected_operational_alerts(emplacements, payload, alert_type):
    """Raise the right alert for each critical telemetry scenario."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message("station/slot1/telemetry", json.dumps(payload))

    assert result["alert_count"] == 1
    alert = Alerte.objects.get(type=alert_type)
    if alert_type != "state_error":
        assert alert.data is not None
        assert alert.data.capteur.device.emplacement == emplacements[0]
