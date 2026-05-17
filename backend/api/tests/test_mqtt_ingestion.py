import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from api.models import (
    Alerte,
    Borne,
    CapteurData,
    Device,
    DeviceCommandLog,
    Emplacement,
    Reservation,
    Session,
    SessionTelemetry,
    Station,
    Technicien,
    TechnicienStation,
)
from api.services.email_notifications import notify_pending_alerts
from api.services.mqtt_commands import build_slot_command_topic
from api.tasks import process_mqtt_message


def test_build_slot_command_topic_accepts_structured_prefix(settings):
    """Build command topics for compact and station/borne MQTT prefixes."""
    settings.MQTT_BASE_TOPIC = "station"

    assert build_slot_command_topic("slot1") == "station/slot1/cmd"
    assert (
        build_slot_command_topic("slot1", topic_prefix="station/station-centre/borne-1")
        == "station/station-centre/borne-1/slot1/cmd"
    )


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
def test_process_mqtt_message_accepts_structured_station_topic(emplacements):
    """Accept production topics that include station and cabinet segments."""
    Device.objects.create(
        emplacement=emplacements[1],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot2",
        status="offline",
    )

    result = process_mqtt_message(
        "station/station-centre/borne-1/slot2/telemetry",
        json.dumps({"state": "charging", "temperature": 29.5, "humidity": 47}),
    )

    assert result["slot_id"] == "slot2"
    assert result["message_type"] == "telemetry"
    assert CapteurData.objects.count() == 2
    assert Device.objects.get(mac_address="slot2").status == "charging"


@pytest.mark.django_db
def test_structured_topic_scopes_duplicate_slot_ids_to_the_expected_borne(emplacements):
    """Use the station/borne topic prefix to avoid mixing identical slot ids."""
    second_station = Station.objects.create(
        nom="Station Est",
        localisation_text="Est",
        statut="active",
    )
    second_borne = Borne.objects.create(
        station=second_station,
        numero=1,
        nom="Borne Est 1",
        mqtt_prefix="station-est/borne-1",
        statut="active",
    )
    second_emplacement = Emplacement.objects.create(
        station=second_station,
        borne=second_borne,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )
    first_device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )
    second_device = Device.objects.create(
        emplacement=second_emplacement,
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/station-est/borne-1/slot1/telemetry",
        json.dumps({"state": "charging", "temperature": 29.5, "humidity": 47}),
    )

    assert result["slot_id"] == "slot1"
    assert result["topic_prefix"] == "station-est/borne-1"
    assert CapteurData.objects.count() == 2
    assert set(CapteurData.objects.values_list("capteur__device_id", flat=True)) == {
        second_device.id_device,
    }
    first_device.refresh_from_db()
    second_device.refresh_from_db()
    assert first_device.status == "offline"
    assert second_device.status == "charging"


@pytest.mark.django_db
def test_process_mqtt_message_ignores_non_supervision_topic(emplacements):
    """Ignore health or diagnostic MQTT topics under the station tree."""
    result = process_mqtt_message("station/health", json.dumps({"status": "ok"}))

    assert result is None
    assert Device.objects.count() == 0
    assert CapteurData.objects.count() == 0


@pytest.mark.django_db
def test_process_mqtt_message_ignores_non_supervision_text_payload(emplacements):
    """Ignore broker healthcheck payloads before trying to parse JSON."""
    result = process_mqtt_message("station/health", "ok")

    assert result is None
    assert Device.objects.count() == 0
    assert CapteurData.objects.count() == 0


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
def test_process_mqtt_status_updates_device_inventory(emplacements):
    """Store ESP32 slot, firmware, hardware MAC and Wi-Fi IP from status payloads."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    process_mqtt_message(
        "station/slot1/status",
        json.dumps(
            {
                "event": "boot",
                "state": "idle",
                "firmware_version": "1.0.1",
                "hardware_mac": "AA:BB:CC:DD:EE:FF",
                "ip_address": "192.168.1.42",
            }
        ),
    )

    device = Device.objects.get(slot_id="slot1")
    assert device.firmware_version == "1.0.1"
    assert device.hardware_mac == "AA:BB:CC:DD:EE:FF"
    assert device.ip_address == "192.168.1.42"


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["access_validated", "waiting_plug"])
def test_process_mqtt_status_accepts_canonical_charge_states(emplacements, state):
    """Map canonical Raspberry charge states to an online device presence."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/slot1/status",
        json.dumps({"state": state}),
    )

    assert result["device_status"] == "online"
    assert Device.objects.get(mac_address="slot1").status == "online"


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
def test_process_mqtt_status_flags_charge_started_without_backend_session(emplacements):
    """Raise a consistency alert when a START reaches charging without backend session."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )

    result = process_mqtt_message(
        "station/slot1/status",
        json.dumps(
            {
                "event": "charging_started",
                "session_id": str(uuid4()),
            }
        ),
    )

    assert result["device_status"] == "charging"
    alert = Alerte.objects.get(type="charge_without_session")
    assert alert.niveau_severite == "critique"
    assert alert.status == "nouvelle"


@pytest.mark.django_db
def test_process_mqtt_ack_tracks_last_command(user, emplacements):
    """Store ESP32 command acknowledgements for supervision traceability."""
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="ACKSESS1",
        auth_choice="qr",
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
        "station/slot1/ack",
        json.dumps(
            {
                "command_id": "cmd-123",
                "action": "START",
                "status": "accepted",
                "message": "Emplacement reserve.",
                "session_id": str(session.id_session),
                "source": "raspberry",
            }
        ),
    )

    device = Device.objects.get(mac_address="slot1")
    assert result["message_type"] == "ack"
    assert result["command_id"] == "cmd-123"
    assert result["command_action"] == "START"
    assert result["command_status"] == "accepted"
    assert device.status == "online"
    assert device.last_command_id == "cmd-123"
    assert device.last_command_action == "START"
    assert device.last_command_status == "accepted"
    assert device.last_command_message == "Emplacement reserve."
    assert device.last_command_at is not None
    command_log = DeviceCommandLog.objects.get()
    assert command_log.device == device
    assert command_log.command_id == "cmd-123"
    assert command_log.action == "START"
    assert command_log.status == "accepted"
    assert command_log.message == "Emplacement reserve."
    assert command_log.session == session
    assert command_log.source == "raspberry"


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
    assert Device.objects.get(emplacement=emplacements[0]).slot_id == "slot1"
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
def test_process_mqtt_message_rejects_unknown_session_id_for_active_slot(user, emplacements):
    """Do not attach ESP32 telemetry to another active session when session_id is unknown."""
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="TELMISS1",
        auth_choice="qr",
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
                "session_id": str(uuid4()),
                "state": "charging",
                "current": 1.35,
                "voltage": 41.7,
                "temperature": 31.5,
                "humidity": 44,
            }
        ),
    )

    assert result["session_telemetry_created"] is False
    assert SessionTelemetry.objects.filter(session=session).count() == 0
    alert = Alerte.objects.get(type="charge_without_session")
    assert alert.status == "nouvelle"
    assert alert.niveau_severite == "critique"
    assert alert.session is None

    resolved_result = process_mqtt_message(
        "station/slot1/telemetry",
        json.dumps(
            {
                "session_id": str(session.id_session),
                "state": "charging",
                "current": 1.2,
                "voltage": 41.5,
            }
        ),
    )

    assert resolved_result["session_telemetry_created"] is True
    alert.refresh_from_db()
    assert alert.status == "resolue"


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
@override_settings(
    ALERT_CRITICAL_NOTIFICATION_MIN_AGE_SECONDS=60,
    ALERT_RENOTIFY_COOLDOWN_SECONDS=3600,
)
def test_process_mqtt_message_sends_alert_email_to_assigned_technicians(
    emplacements,
    django_capture_on_commit_callbacks,
):
    """Notify station technicians only after an alert persists long enough."""
    station = emplacements[0].station
    technician = Technicien.objects.create(
        nom="Technicien Centre",
        email="tech-centre@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technician, station=station)
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )
    first_seen = timezone.now() - timedelta(minutes=2)

    with django_capture_on_commit_callbacks(execute=True):
        first_result = process_mqtt_message(
            "station/slot1/telemetry",
            json.dumps(
                {
                    "state": "charging",
                    "door": False,
                    "cable": True,
                    "timestamp": first_seen.isoformat(),
                }
            ),
        )

    assert first_result["alert_count"] == 1
    assert mail.outbox == []

    with django_capture_on_commit_callbacks(execute=True):
        second_result = process_mqtt_message(
            "station/slot1/telemetry",
            json.dumps(
                {
                    "state": "charging",
                    "door": False,
                    "cable": True,
                    "timestamp": timezone.now().isoformat(),
                }
            ),
        )

    assert second_result["alert_count"] == 0
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["tech-centre@example.com"]
    assert "Station Centre" in message.subject
    assert "intrusion" in message.body
    assert "Borne 1" in message.body
    assert "Emplacement 1" in message.body
    alert = Alerte.objects.get(type="intrusion")
    assert alert.status == "active"
    assert alert.notification_count == 1
    assert alert.notified_at is not None


@pytest.mark.django_db
@override_settings(ALERT_NOTIFICATION_MIN_AGE_SECONDS=60)
def test_send_alert_notifications_command_processes_pending_alerts(emplacements):
    """Send delayed emails for active alerts that were not notified yet."""
    station = emplacements[0].station
    technician = Technicien.objects.create(
        nom="Technicien Centre",
        email="tech-centre@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technician, station=station)
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )
    capteur = device.capteurs.create(type="current", unite="A")
    data = CapteurData.objects.create(
        capteur=capteur,
        valeur=3.5,
        timestamp=timezone.now() - timedelta(minutes=3),
    )
    Alerte.objects.create(
        data=data,
        type="overcurrent",
        message="Surconsommation detectee: 3.50 A.",
        niveau_severite="haute",
        status="active",
        timestamp=timezone.now() - timedelta(minutes=3),
        first_seen=timezone.now() - timedelta(minutes=3),
        last_seen=timezone.now() - timedelta(minutes=1),
    )

    call_command("send_alert_notifications")

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["tech-centre@example.com"]
    alert = Alerte.objects.get(type="overcurrent")
    assert alert.notification_count == 1


@pytest.mark.django_db
@override_settings(ALERT_NOTIFICATION_MIN_AGE_SECONDS=60)
def test_notify_pending_alerts_respects_policy_delay(emplacements):
    """Keep short-lived active alerts silent until their persistence delay expires."""
    station = emplacements[0].station
    technician = Technicien.objects.create(
        nom="Technicien Centre",
        email="tech-centre@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technician, station=station)
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="demo",
        mac_address="slot1",
        status="offline",
    )
    capteur = device.capteurs.create(type="current", unite="A")
    data = CapteurData.objects.create(
        capteur=capteur,
        valeur=3.5,
        timestamp=timezone.now(),
    )
    Alerte.objects.create(
        data=data,
        type="overcurrent",
        message="Surconsommation detectee: 3.50 A.",
        niveau_severite="haute",
        status="active",
        timestamp=timezone.now(),
        first_seen=timezone.now(),
        last_seen=timezone.now(),
    )

    result = notify_pending_alerts()

    assert result == {"alerts_notified": 0, "emails_sent": 0}
    assert mail.outbox == []


@pytest.mark.django_db
@override_settings(EXPECTED_ESP32_FIRMWARE_VERSION="2.0.0")
def test_process_mqtt_status_creates_and_resolves_firmware_alert(emplacements):
    """Raise firmware alerts for admins and resolve them when the ESP32 is updated."""
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot1",
        status="offline",
    )

    process_mqtt_message(
        "station/slot1/status",
        json.dumps({"state": "idle", "firmware_version": "1.0.0"}),
    )

    alert = Alerte.objects.get(type="firmware_outdated")
    assert alert.status == "nouvelle"
    assert alert.niveau_severite == "moyenne"
    assert "attendu 2.0.0" in alert.message
    assert mail.outbox == []

    process_mqtt_message(
        "station/slot1/status",
        json.dumps({"state": "idle", "firmware_version": "2.0.0"}),
    )

    alert.refresh_from_db()
    assert alert.status == "resolue"
    assert Device.objects.get(mac_address="slot1").firmware_version == "2.0.0"


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
