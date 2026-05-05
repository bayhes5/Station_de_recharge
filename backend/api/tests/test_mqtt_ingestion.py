import json

import pytest

from api.models import CapteurData, Device
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
                "door": True,
                "cable": True,
            }
        ),
    )

    assert result["slot_id"] == "slot1"
    assert result["capteur_count"] == 4
    assert CapteurData.objects.count() == 4
    assert Device.objects.get(mac_address="slot1").status == "charging"


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
