import json
from datetime import timedelta

import pytest
from django.utils import timezone

from api.models import Alerte, CapteurData, Device, Reservation, Session, SessionTelemetry
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
def test_process_mqtt_status_updates_device_presence(emplacements):
    """Use ESP32 status events as heartbeat even before sensor telemetry arrives."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/slot1/status",
        json.dumps({"event": "reserved", "state": "reserved"}),
    )

    device = Device.objects.get(mac_address="slot1")
    assert result["message_type"] == "status"
    assert result["capteur_count"] == 0
    assert device.status == "online"
    assert device.last_seen is not None


@pytest.mark.django_db
def test_process_mqtt_status_maps_charging_started(emplacements):
    """Reflect the ESP32 charging state as soon as it reports charge start."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/slot1/status",
        json.dumps({"event": "charging_started", "state": "charging"}),
    )

    assert result["device_status"] == "charging"
    assert Device.objects.get(mac_address="slot1").status == "charging"


@pytest.mark.django_db
def test_process_mqtt_alert_topic_creates_operational_alert(emplacements):
    """Ingest explicit ESP32 alert topics from the local broker."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="charging",
    )

    result = process_mqtt_message(
        "station/slot1/alert",
        json.dumps({"type": "overheat", "state": "error", "session_id": "offline-local"}),
    )

    device = Device.objects.get(mac_address="slot1")
    assert result["message_type"] == "alert"
    assert result["alert_count"] == 1
    assert device.status == "error"
    assert Alerte.objects.get(type="state_error").status == "nouvelle"


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
def test_process_mqtt_message_stores_session_telemetry_for_active_session(user, emplacements):
    """Attach electrical telemetry to the active charging session for Grafana."""
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="TELSESS1",
        auth_choice="rfid",
        date_debut=timezone.now() - timedelta(minutes=10),
        date_fin=timezone.now() + timedelta(minutes=20),
        statut="active",
    )
    session = Session.objects.create(
        reservation=reservation,
        emplacement=emplacements[0],
        start_time=timezone.now() - timedelta(minutes=5),
    )
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
                "session_id": str(session.id_session),
                "state": "charging",
                "current": 1.35,
                "voltage": 41.7,
                "energy_kwh": 0.12,
                "temperature": 31.5,
                "humidity": 44,
            }
        ),
    )

    assert result["session_telemetry_created"] is True
    telemetry = SessionTelemetry.objects.get(session=session)
    assert telemetry.courant == 1.35
    assert telemetry.tension == 41.7
    assert telemetry.energie_kwh == 0.12


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
