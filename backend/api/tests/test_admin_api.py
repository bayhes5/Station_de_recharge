from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import (
    Alerte,
    AlertStatus,
    Authentification,
    Borne,
    Capteur,
    CapteurData,
    Device,
    DeviceCommandLog,
    Emplacement,
    FirmwareUpdateStatus,
    JournalSecurite,
    Maintenance,
    ProfilUtilisateur,
    Reservation,
    Session,
    SessionTelemetry,
    Station,
    Technicien,
    TechnicienStation,
    TypeAuth,
)


def hash_secret(value):
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.mark.django_db
def test_admin_overview_requires_staff(authenticated_client):
    response = authenticated_client.get(reverse("api-admin-overview"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_overview_returns_counts(admin_client, station, emplacements):
    response = admin_client.get(reverse("api-admin-overview"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stats"]["stations_total"] == 1
    assert response.data["stats"]["bornes_total"] == 1
    assert response.data["stats"]["emplacements_total"] == 3


@pytest.mark.django_db
def test_admin_supervision_requires_staff(authenticated_client):
    response = authenticated_client.get(reverse("api-admin-supervision"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_operational_export_supports_json_and_csv(admin_client, station, emplacements):
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.4.0",
        mac_address="slot-export",
        slot_id="slot-export",
        last_seen=timezone.now(),
        status="idle",
    )

    json_response = admin_client.get(
        reverse("api-admin-export-operational"),
        {"export_format": "json", "station_id": str(station.id_station)},
    )
    csv_response = admin_client.get(
        reverse("api-admin-export-operational"),
        {"export_format": "csv", "station_id": str(station.id_station)},
    )

    assert json_response.status_code == status.HTTP_200_OK
    assert json_response.data["summary"]["stations_total"] == 1
    assert json_response.data["rows"][0]["station"] == "Station Centre"
    assert csv_response.status_code == status.HTTP_200_OK
    assert "text/csv" in csv_response["Content-Type"]
    assert "slot-export" in csv_response.content.decode("utf-8")


@pytest.mark.django_db
def test_admin_export_previews_and_downloads_filtered_security_logs(admin_client, user):
    JournalSecurite.objects.create(
        utilisateur=user,
        action="user:test:sms_access_code_sent:DEMO1",
        ip="127.0.0.1",
        statut="success",
    )
    JournalSecurite.objects.create(
        utilisateur=user,
        action="user:test:login_failed",
        ip="127.0.0.2",
        statut="failure",
    )

    preview_response = admin_client.get(
        reverse("api-admin-export-operational"),
        {
            "dataset": "security_logs",
            "query": "sms_access",
            "log_status": "success",
            "export_format": "json",
        },
    )
    csv_response = admin_client.get(
        reverse("api-admin-export-operational"),
        {
            "dataset": "security_logs",
            "query": "sms_access",
            "log_status": "success",
            "export_format": "csv",
            "download": "1",
        },
    )

    assert preview_response.status_code == status.HTTP_200_OK
    assert preview_response.data["metadata"]["dataset"] == "security_logs"
    assert preview_response.data["summary"]["total_matches"] == 1
    assert preview_response.data["rows"][0]["action"] == "user:test:sms_access_code_sent:DEMO1"
    assert csv_response.status_code == status.HTTP_200_OK
    assert "journaux-securite-archives.csv" in csv_response["Content-Disposition"]
    assert "sms_access_code_sent" in csv_response.content.decode("utf-8")
    assert JournalSecurite.objects.filter(action__contains="export:security_logs").exists()


@pytest.mark.django_db
def test_admin_supervision_returns_devices_alerts_and_measurements(admin_client, user, emplacements):
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        ip_address="192.168.40.10",
        mac_address="slot1",
        last_seen=timezone.now(),
        status="charging",
    )
    capteur = Capteur.objects.create(device=device, type="temperature", unite="C")
    data = CapteurData.objects.create(capteur=capteur, valeur=42.5)
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("SUPERVISION"),
        display_value="****SION",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="SUPERV1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=10),
        date_fin=timezone.now() + timedelta(minutes=20),
        statut="confirmee",
    )
    session = Session.objects.create(
        reservation=reservation,
        emplacement=emplacements[0],
        start_time=timezone.now() - timedelta(minutes=5),
    )
    Alerte.objects.create(
        data=data,
        session=session,
        type="overheat",
        message="Température élevée",
        niveau_severite="critical",
        status="active",
    )

    response = admin_client.get(reverse("api-admin-supervision"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stats"]["devices_total"] == 1
    assert response.data["stats"]["devices_online"] == 1
    assert response.data["stats"]["active_alerts"] == 1
    assert response.data["devices"][0]["slot_id"] == "slot1"
    assert response.data["devices"][0]["slot_label"] == "Station Centre - Borne 1 - emplacement 1"
    assert response.data["devices"][0]["station_id"] == str(emplacements[0].station_id)
    assert response.data["devices"][0]["borne_nom"] == "Borne 1"
    assert response.data["devices"][0]["status_display"] == "Charge en cours"
    assert response.data["alerts"][0]["type"] == "overheat"
    assert response.data["alerts"][0]["station_id"] == str(emplacements[0].station_id)
    assert response.data["alerts"][0]["station_nom"] == "Station Centre"
    assert response.data["alerts"][0]["emplacement_numero"] == 1
    assert response.data["measurements"][0]["type"] == "temperature"
    assert response.data["measurements"][0]["station_id"] == str(emplacements[0].station_id)
    assert response.data["measurements"][0]["slot_label"] == "Station Centre - Borne 1 - emplacement 1"


@pytest.mark.django_db
def test_admin_sessions_include_latest_session_telemetry(admin_client, user, emplacements):
    """Expose the latest electrical sample so the admin session view refreshes live."""
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("SESSION1"),
        display_value="****ION1",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="SESSION1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=10),
        date_fin=timezone.now() + timedelta(minutes=20),
        statut="confirmee",
    )
    session = Session.objects.create(
        reservation=reservation,
        emplacement=emplacements[0],
        start_time=timezone.now() - timedelta(minutes=5),
    )
    SessionTelemetry.objects.create(
        session=session,
        courant=1.2,
        tension=12.0,
        energie_kwh=0.01,
        timestamp=timezone.now() - timedelta(minutes=2),
    )
    latest = SessionTelemetry.objects.create(
        session=session,
        courant=1.8,
        tension=12.1,
        energie_kwh=0.02,
        timestamp=timezone.now(),
    )

    response = admin_client.get(reverse("api-admin-sessions"))

    assert response.status_code == status.HTTP_200_OK
    telemetry = response.data["active"][0]["latest_telemetry"]
    assert telemetry["courant"] == latest.courant
    assert telemetry["tension"] == latest.tension
    assert telemetry["energie_kwh"] == latest.energie_kwh
    assert telemetry["puissance_w"] == pytest.approx(latest.courant * latest.tension)


@pytest.mark.django_db
def test_admin_supervision_resolves_alert_location_from_sensor_data(admin_client, emplacements):
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot1",
        last_seen=timezone.now(),
        status="charging",
    )
    capteur = Capteur.objects.create(device=device, type="current", unite="A")
    data = CapteurData.objects.create(capteur=capteur, valeur=3.4)
    Alerte.objects.create(
        data=data,
        type="overcurrent",
        message="Surconsommation détectée",
        niveau_severite="haute",
        status="nouvelle",
    )

    response = admin_client.get(reverse("api-admin-supervision"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["alerts"][0]["station_nom"] == "Station Centre"
    assert response.data["alerts"][0]["emplacement_numero"] == 1


@pytest.mark.django_db
def test_admin_supervision_formats_boolean_sensor_measurements(admin_client, emplacements):
    """Expose readable values for boolean door and cable sensor samples."""
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot1",
        last_seen=timezone.now(),
        status="charging",
    )
    door = Capteur.objects.create(device=device, type="door", unite="bool")
    cable = Capteur.objects.create(device=device, type="cable", unite="bool")
    CapteurData.objects.create(capteur=door, valeur=0)
    CapteurData.objects.create(capteur=cable, valeur=1)

    response = admin_client.get(reverse("api-admin-supervision"))

    assert response.status_code == status.HTTP_200_OK
    display_values = {measurement["type"]: measurement["display_value"] for measurement in response.data["measurements"]}
    assert display_values["door"] == "Boîtier ouvert"
    assert display_values["cable"] == "Câble présent"


@pytest.mark.django_db
def test_admin_supervision_marks_stale_devices_offline(admin_client, emplacements):
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        ip_address="192.168.40.10",
        mac_address="slot1",
        last_seen=timezone.now() - timedelta(minutes=30),
        status="charging",
    )

    response = admin_client.get(reverse("api-admin-supervision"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stats"]["devices_online"] == 0
    assert response.data["stats"]["devices_offline"] == 1
    assert response.data["devices"][0]["health"] == "offline"
    assert response.data["devices"][0]["status_display"] == "Charge en cours"


@pytest.mark.django_db
def test_admin_supervision_marks_never_seen_devices_waiting_for_telemetry(admin_client, emplacements):
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        ip_address="192.168.40.10",
        mac_address="slot1",
        status="online",
    )

    response = admin_client.get(reverse("api-admin-supervision"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stats"]["devices_online"] == 0
    assert response.data["stats"]["devices_offline"] == 1
    assert response.data["devices"][0]["health"] == "offline"
    assert response.data["devices"][0]["status_display"] == "Aucune télémétrie reçue"


@pytest.mark.django_db
def test_admin_devices_requires_staff(authenticated_client):
    response = authenticated_client.get(reverse("api-admin-devices"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_devices_exposes_firmware_policy(admin_client, emplacements):
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        expected_firmware_version="1.1.0",
        firmware_update_status=FirmwareUpdateStatus.UPDATE_REQUIRED,
        mac_address="slot1",
        status="offline",
    )

    response = admin_client.get(reverse("api-admin-devices"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"][0]["id_device"] == str(device.id_device)
    assert response.data["results"][0]["firmware_version"] == "1.0.0"
    assert response.data["results"][0]["effective_expected_firmware_version"] == "1.1.0"
    assert response.data["results"][0]["firmware_update_required"] is True


@pytest.mark.django_db
def test_admin_can_schedule_ota_update(admin_client, emplacements):
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot1",
        status="offline",
    )

    response = admin_client.post(
        reverse("api-admin-device-schedule-ota", kwargs={"device_id": device.id_device}),
        {
            "target_version": "1.2.0",
            "update_url": "https://updates.example.local/esp32-1.2.0.bin",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["expected_firmware_version"] == "1.2.0"
    assert response.data["ota_target_version"] == "1.2.0"
    assert response.data["firmware_update_status"] == FirmwareUpdateStatus.UPDATE_SCHEDULED
    device.refresh_from_db()
    assert device.ota_requested_at is not None


@pytest.mark.django_db
def test_admin_device_patch_updates_firmware_compliance_status(admin_client, emplacements):
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot1",
        status="offline",
    )

    response = admin_client.patch(
        reverse("api-admin-device-detail", kwargs={"device_id": device.id_device}),
        {"expected_firmware_version": "1.0.0"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["firmware_update_status"] == FirmwareUpdateStatus.UP_TO_DATE


@pytest.mark.django_db
def test_admin_can_assign_station_to_technician(admin_client, admin_user, station):
    technicien = Technicien.objects.create(
        utilisateur=admin_user,
        nom="Tech Centre",
        email="tech-centre@example.com",
        telephone="0600000000",
    )

    response = admin_client.post(
        reverse("api-admin-technician-station-assignments"),
        {
            "technicien": str(technicien.id_technicien),
            "station": str(station.id_station),
            "role": "referent",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["station_nom"] == "Station Centre"
    assert response.data["technicien_nom"] == "Tech Centre"
    assert response.data["role"] == "referent"
    assert TechnicienStation.objects.filter(technicien=technicien, station=station, is_active=True).exists()


@pytest.mark.django_db
def test_admin_rejects_duplicate_technician_station_assignment(admin_client, admin_user, station):
    technicien = Technicien.objects.create(
        utilisateur=admin_user,
        nom="Tech Duplicate",
        email="tech-duplicate@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technicien, station=station)

    response = admin_client.post(
        reverse("api-admin-technician-station-assignments"),
        {
            "technicien": str(technicien.id_technicien),
            "station": str(station.id_station),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data


@pytest.mark.django_db
def test_admin_can_create_technician_with_station_scope(admin_client, admin_user, station):
    response = admin_client.post(
        reverse("api-admin-technicians"),
        {
            "utilisateur": str(admin_user.id_user),
            "nom": "Tech Scoped",
            "email": "tech-scoped@example.com",
            "telephone": "0600000000",
            "station_scope": [str(station.id_station)],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    technician = Technicien.objects.get(email="tech-scoped@example.com")
    assert TechnicienStation.objects.filter(
        technicien=technician,
        station=station,
        is_active=True,
    ).exists()
    assert response.data["assigned_stations"][0]["station_nom"] == "Station Centre"


@pytest.mark.django_db
def test_admin_can_update_technician_station_scope(admin_client, admin_user, station):
    technician = Technicien.objects.create(
        utilisateur=admin_user,
        nom="Tech Update Scope",
        email="tech-update-scope@example.com",
        telephone="",
    )
    existing_assignment = TechnicienStation.objects.create(
        technicien=technician,
        station=station,
        role="referent",
    )
    other_station = Station.objects.create(
        nom="Station Est",
        localisation_text="Quartier Est",
        statut="active",
    )

    response = admin_client.patch(
        reverse("api-admin-technician-detail", kwargs={"technician_id": technician.id_technicien}),
        {"station_scope": [str(other_station.id_station)]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    existing_assignment.refresh_from_db()
    assert existing_assignment.is_active is False
    assert TechnicienStation.objects.get(
        technicien=technician,
        station=other_station,
    ).is_active is True
    assert [assignment["station_nom"] for assignment in response.data["assigned_stations"]] == [
        "Station Est"
    ]


@pytest.mark.django_db
def test_admin_technician_update_without_station_scope_keeps_assignments(
    admin_client,
    admin_user,
    station,
):
    technician = Technicien.objects.create(
        utilisateur=admin_user,
        nom="Tech Keep Scope",
        email="tech-keep-scope@example.com",
        telephone="",
    )
    assignment = TechnicienStation.objects.create(technicien=technician, station=station)

    response = admin_client.patch(
        reverse("api-admin-technician-detail", kwargs={"technician_id": technician.id_technicien}),
        {"telephone": "0611111111"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assignment.refresh_from_db()
    assert assignment.is_active is True


@pytest.mark.django_db
def test_technician_supervision_is_limited_to_assigned_stations(api_client, user, station, borne, emplacements):
    technicien = Technicien.objects.create(
        utilisateur=user,
        nom="Tech Scope",
        email="tech-scope@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technicien, station=station)
    other_station = Station.objects.create(
        nom="Station Nord",
        localisation_text="Quartier Nord",
        statut="active",
    )
    other_borne = Borne.objects.create(
        station=other_station,
        numero=1,
        nom="Borne Nord",
        statut="active",
    )
    other_emplacement = Emplacement.objects.create(
        station=other_station,
        borne=other_borne,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )
    assigned_device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot-assigned",
        last_seen=timezone.now(),
        status="charging",
    )
    other_device = Device.objects.create(
        emplacement=other_emplacement,
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot-other",
        last_seen=timezone.now(),
        status="charging",
    )
    assigned_capteur = Capteur.objects.create(device=assigned_device, type="temperature", unite="C")
    other_capteur = Capteur.objects.create(device=other_device, type="temperature", unite="C")
    assigned_data = CapteurData.objects.create(capteur=assigned_capteur, valeur=31)
    CapteurData.objects.create(capteur=other_capteur, valeur=38)
    Alerte.objects.create(
        data=assigned_data,
        type="overheat",
        message="Température élevée",
        niveau_severite="haute",
        status="active",
    )
    DeviceCommandLog.objects.create(
        device=assigned_device,
        command_id="cmd-assigned",
        action="START",
        status="accepted",
        source="esp32",
    )
    DeviceCommandLog.objects.create(
        device=other_device,
        command_id="cmd-other",
        action="START",
        status="accepted",
        source="esp32",
    )
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("api-technician-supervision"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["scope"]["restricted"] is True
    assert response.data["stats"]["devices_total"] == 1
    assert response.data["devices"][0]["slot_id"] == "slot-assigned"
    assert response.data["measurements"][0]["slot_id"] == "slot-assigned"
    assert response.data["commands"][0]["command_id"] == "cmd-assigned"
    assert {row["station_nom"] for row in response.data["devices"]} == {"Station Centre"}


@pytest.mark.django_db
def test_technician_supervision_requires_technician_profile(authenticated_client):
    response = authenticated_client.get(reverse("api-technician-supervision"))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_technician_can_acknowledge_and_resolve_scoped_alert(api_client, user, station, emplacements):
    technicien = Technicien.objects.create(
        utilisateur=user,
        nom="Tech Alert",
        email="tech-alert@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technicien, station=station)
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot1",
        status="charging",
    )
    capteur = Capteur.objects.create(device=device, type="temperature", unite="C")
    data = CapteurData.objects.create(capteur=capteur, valeur=65)
    alert = Alerte.objects.create(
        data=data,
        type="overheat",
        message="Température élevée",
        niveau_severite="critique",
        status=AlertStatus.ACTIVE,
    )
    api_client.force_authenticate(user=user)

    acknowledge_response = api_client.post(
        reverse("api-technician-alert-acknowledge", kwargs={"alert_id": alert.id_alerte})
    )

    assert acknowledge_response.status_code == status.HTTP_200_OK
    alert.refresh_from_db()
    assert alert.status == AlertStatus.IN_PROGRESS
    assert alert.assigned_technician == technicien
    assert alert.acknowledged_by == technicien
    assert alert.acknowledged_at is not None
    assert acknowledge_response.data["alert"]["status"] == AlertStatus.IN_PROGRESS

    resolve_response = api_client.post(
        reverse("api-technician-alert-resolve", kwargs={"alert_id": alert.id_alerte}),
        {"note": "Boitier controle sur site."},
        format="json",
    )

    assert resolve_response.status_code == status.HTTP_200_OK
    alert.refresh_from_db()
    assert alert.status == AlertStatus.RESOLVED
    assert alert.resolved_by == technicien
    assert alert.resolved_at is not None
    assert alert.resolution_note == "Boitier controle sur site."
    assert resolve_response.data["alert"]["resolution_note"] == "Boitier controle sur site."


@pytest.mark.django_db
def test_observer_technician_can_read_but_not_process_alert(api_client, user, station, emplacements):
    technicien = Technicien.objects.create(
        utilisateur=user,
        nom="Tech Lecture",
        email="tech-lecture@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technicien, station=station, role="observateur")
    device = Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot-observer",
        status="charging",
    )
    capteur = Capteur.objects.create(device=device, type="temperature", unite="C")
    data = CapteurData.objects.create(capteur=capteur, valeur=65)
    alert = Alerte.objects.create(
        data=data,
        type="overheat",
        message="Température élevée",
        niveau_severite="critique",
        status=AlertStatus.ACTIVE,
    )
    api_client.force_authenticate(user=user)

    supervision_response = api_client.get(reverse("api-technician-supervision"))
    acknowledge_response = api_client.post(
        reverse("api-technician-alert-acknowledge", kwargs={"alert_id": alert.id_alerte})
    )

    assert supervision_response.status_code == status.HTTP_200_OK
    assert supervision_response.data["alerts"][0]["type"] == "overheat"
    assert acknowledge_response.status_code == status.HTTP_403_FORBIDDEN
    alert.refresh_from_db()
    assert alert.status == AlertStatus.ACTIVE


@pytest.mark.django_db
def test_technician_cannot_manage_alert_outside_assigned_station(api_client, user, station, emplacements):
    technicien = Technicien.objects.create(
        utilisateur=user,
        nom="Tech Scope Alert",
        email="tech-scope-alert@example.com",
        telephone="",
    )
    TechnicienStation.objects.create(technicien=technicien, station=station)
    other_station = Station.objects.create(
        nom="Station Ouest",
        localisation_text="Quartier Ouest",
        statut="active",
    )
    other_borne = Borne.objects.create(
        station=other_station,
        numero=1,
        nom="Borne Ouest",
        statut="active",
    )
    other_emplacement = Emplacement.objects.create(
        station=other_station,
        borne=other_borne,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )
    other_device = Device.objects.create(
        emplacement=other_emplacement,
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot-other",
        status="charging",
    )
    capteur = Capteur.objects.create(device=other_device, type="temperature", unite="C")
    data = CapteurData.objects.create(capteur=capteur, valeur=65)
    alert = Alerte.objects.create(
        data=data,
        type="overheat",
        message="Température élevée",
        niveau_severite="critique",
        status=AlertStatus.ACTIVE,
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("api-technician-alert-acknowledge", kwargs={"alert_id": alert.id_alerte})
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    alert.refresh_from_db()
    assert alert.status == AlertStatus.ACTIVE


@pytest.mark.django_db
def test_admin_can_create_user(admin_client):
    response = admin_client.post(
        reverse("api-admin-users"),
        {
            "pseudo": "created",
            "email": "created@example.com",
            "password": "CreatedPass123!",
            "nom": "Created User",
            "telephone": "0600000000",
            "is_staff": False,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = get_user_model().objects.get(pseudo="created")
    assert user.email == "created@example.com"
    assert user.check_password("CreatedPass123!")
    assert user.profil.nom == "Created User"


@pytest.mark.django_db
def test_admin_user_create_requires_required_fields(admin_client):
    response = admin_client.post(
        reverse("api-admin-users"),
        {"pseudo": "missing-password", "email": "missing@example.com"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_admin_user_create_rejects_invalid_status(admin_client):
    response = admin_client.post(
        reverse("api-admin-users"),
        {
            "pseudo": "invalid-status",
            "email": "invalid-status@example.com",
            "password": "AdminPass123!",
            "statut": "enabled",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "statut" in response.data


@pytest.mark.django_db
def test_staff_admin_cannot_create_privileged_user(admin_client):
    response = admin_client.post(
        reverse("api-admin-users"),
        {
            "pseudo": "privileged",
            "email": "privileged@example.com",
            "password": "PrivilegedPass123!",
            "is_superuser": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not get_user_model().objects.filter(pseudo="privileged").exists()


@pytest.mark.django_db
def test_admin_can_patch_user(admin_client, user):
    ProfilUtilisateur.objects.create(utilisateur=user, nom="Old", telephone="")

    response = admin_client.patch(
        reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}),
        {"nom": "Updated User"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.is_staff is False
    assert user.profil.nom == "Updated User"


@pytest.mark.django_db
def test_staff_admin_cannot_grant_privileged_roles(admin_client, user):
    response = admin_client.patch(
        reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}),
        {"is_staff": True},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    user.refresh_from_db()
    assert user.is_staff is False


@pytest.mark.django_db
def test_superadmin_can_grant_privileged_roles(api_client, user):
    superadmin = get_user_model().objects.create_superuser(
        pseudo="superadmin",
        email="superadmin@example.com",
        password="SuperAdminPass123!",
    )
    api_client.force_authenticate(user=superadmin)

    response = api_client.patch(
        reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}),
        {"is_staff": True},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.is_staff is True


@pytest.mark.django_db
def test_admin_can_mark_phone_number_as_verified(admin_client, user):
    ProfilUtilisateur.objects.create(
        utilisateur=user,
        nom="User",
        telephone="+33600000000",
        telephone_verifie=False,
    )

    response = admin_client.patch(
        reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}),
        {"telephone_verifie": True},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.profil.refresh_from_db()
    assert user.profil.telephone_verifie is True


@pytest.mark.django_db
def test_admin_can_anonymize_user(admin_client):
    user = get_user_model().objects.create_user(
        pseudo="delete-me",
        email="delete-me@example.com",
        password="DeletePass123!",
    )

    response = admin_client.delete(reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert get_user_model().objects.filter(id_user=user.id_user).exists()
    user.refresh_from_db()
    assert user.is_active is False
    assert user.email.endswith("@anonymized.invalid")

    list_response = admin_client.get(reverse("api-admin-users"))
    assert list_response.status_code == status.HTTP_200_OK
    assert not any(str(item["id_user"]) == str(user.id_user) for item in list_response.data["results"])

    detail_response = admin_client.get(reverse("api-admin-user-detail", kwargs={"user_id": user.id_user}))
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.data["pseudo"] == "Compte supprimé"
    assert detail_response.data["email"] == ""
    assert detail_response.data["nom"] == "Compte supprimé"
    assert detail_response.data["is_deleted"] is True


@pytest.mark.django_db
def test_admin_can_list_create_and_revoke_user_rfid(admin_client, admin_user, user):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    old_badge = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("OLD-RFID"),
        display_value="OLD-RFID",
        expiration=timezone.now() + timedelta(days=365),
    )

    create_response = admin_client.post(
        reverse("api-admin-user-auth-methods", kwargs={"user_id": user.id_user}),
        {"auth_value": "RFID-SECRET-1234"},
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["auth_method"]["display_value"] == "****1234"
    auth_id = create_response.data["auth_method"]["id_auth"]
    old_badge.refresh_from_db()
    assert old_badge.is_active is False

    list_response = admin_client.get(reverse("api-admin-user-auth-methods", kwargs={"user_id": user.id_user}))

    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.data["results"][0]["display_value"] == "****1234"
    assert "RFID-SECRET-1234" not in str(list_response.data)

    revoke_response = admin_client.post(
        reverse(
            "api-admin-user-auth-method-revoke",
            kwargs={"user_id": user.id_user, "auth_id": auth_id},
        )
    )

    assert revoke_response.status_code == status.HTTP_204_NO_CONTENT
    auth_method = Authentification.objects.get(id_auth=auth_id)
    assert auth_method.is_active is False
    assert JournalSecurite.objects.filter(
        utilisateur=user,
        action__contains=f"admin:{admin_user.pseudo}:rfid_revoked",
    ).exists()


@pytest.mark.django_db
def test_admin_can_regenerate_and_revoke_temporary_access(admin_client, admin_user, user, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("OLD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="ADMINCD1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() + timedelta(minutes=10),
        date_fin=timezone.now() + timedelta(minutes=40),
        statut="confirmee",
    )

    regenerate_response = admin_client.post(
        reverse("api-admin-reservation-access-payload", kwargs={"reservation_id": reservation.id_reservation})
    )

    assert regenerate_response.status_code == status.HTTP_200_OK
    assert regenerate_response.data["message"] == "Accès temporaire régénéré."
    assert "access_payload" not in regenerate_response.data
    reservation.refresh_from_db()
    reservation.authentification.refresh_from_db()
    assert reservation.authentification.is_active is True

    revoke_response = admin_client.post(
        reverse("api-admin-reservation-access-revoke", kwargs={"reservation_id": reservation.id_reservation})
    )

    assert revoke_response.status_code == status.HTTP_200_OK
    reservation.authentification.refresh_from_db()
    assert reservation.authentification.is_active is False
    assert JournalSecurite.objects.filter(
        utilisateur=user,
        action__contains=f"admin:{admin_user.pseudo}:temporary_access_revoked",
    ).exists()


@pytest.mark.django_db
def test_admin_archived_reservation_access_is_not_active(admin_client, user, emplacements):
    type_auth = TypeAuth.objects.create(libelle="QR", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("archived-qr-secret"),
        display_value="QR-demo",
        expiration=timezone.now() + timedelta(days=1),
        is_active=True,
    )
    Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="ARCHQR1",
        authentification=auth_method,
        auth_choice="qr",
        date_debut=timezone.now() - timedelta(hours=2),
        date_fin=timezone.now() - timedelta(hours=1),
        statut="terminee",
    )

    response = admin_client.get(reverse("api-admin-reservations"))

    assert response.status_code == status.HTTP_200_OK
    archived = next(item for item in response.data["archived"] if item["reference_code"] == "ARCHQR1")
    assert archived["auth_is_active"] is False
    assert archived["can_cancel"] is False


@pytest.mark.django_db
def test_admin_started_reservation_stays_operational_until_slot_end(admin_client, user, emplacements):
    type_auth = TypeAuth.objects.create(libelle="QR", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("started-qr-secret"),
        display_value="QR-started",
        expiration=timezone.now() + timedelta(days=1),
        is_active=True,
    )
    Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="STARTQR1",
        authentification=auth_method,
        auth_choice="qr",
        date_debut=timezone.now() - timedelta(minutes=15),
        date_fin=timezone.now() + timedelta(minutes=45),
        statut="active",
    )

    response = admin_client.get(reverse("api-admin-reservations"))

    assert response.status_code == status.HTTP_200_OK
    assert not any(item["reference_code"] == "STARTQR1" for item in response.data["archived"])
    operational = next(item for item in response.data["upcoming"] if item["reference_code"] == "STARTQR1")
    assert operational["auth_is_active"] is True
    assert operational["can_cancel"] is False


@pytest.mark.django_db
def test_admin_can_crud_station(admin_client):
    create_response = admin_client.post(
        reverse("api-admin-stations"),
        {
            "nom": "Station Nord",
            "localisation_text": "Quartier Nord",
            "latitude": 48.9,
            "longitude": 2.4,
            "statut": "active",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    station_id = create_response.data["id_station"]

    patch_response = admin_client.patch(
        reverse("api-admin-station-detail", kwargs={"station_id": station_id}),
        {"statut": "maintenance"},
        format="json",
    )

    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["statut"] == "maintenance"

    delete_response = admin_client.delete(reverse("api-admin-station-detail", kwargs={"station_id": station_id}))

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not Station.objects.filter(id_station=station_id).exists()


@pytest.mark.django_db
def test_admin_can_crud_borne(admin_client, station):
    create_response = admin_client.post(
        reverse("api-admin-bornes"),
        {
            "station": str(station.id_station),
            "numero": 2,
            "nom": "Borne rapide",
            "mqtt_prefix": "station-centre/borne-2",
            "statut": "active",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    borne_id = create_response.data["id_borne"]
    assert create_response.data["station_nom"] == "Station Centre"

    patch_response = admin_client.patch(
        reverse("api-admin-borne-detail", kwargs={"borne_id": borne_id}),
        {"statut": "maintenance"},
        format="json",
    )

    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["statut"] == "maintenance"

    delete_response = admin_client.delete(reverse("api-admin-borne-detail", kwargs={"borne_id": borne_id}))

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not Borne.objects.filter(id_borne=borne_id).exists()


@pytest.mark.django_db
def test_admin_can_filter_bornes_and_emplacements_by_station(admin_client, station, borne, emplacements):
    other_station = Station.objects.create(
        nom="Station Est",
        localisation_text="Quartier Est",
        latitude=49.0,
        longitude=2.5,
        statut="active",
    )
    other_borne = Borne.objects.create(
        station=other_station,
        numero=1,
        nom="Borne Est",
        mqtt_prefix="station-est/borne-1",
        statut="active",
    )
    other_emplacement = Emplacement.objects.create(
        station=other_station,
        borne=other_borne,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )

    bornes_response = admin_client.get(reverse("api-admin-bornes"), {"station": str(station.id_station)})
    emplacements_response = admin_client.get(reverse("api-admin-emplacements"), {"station": str(station.id_station)})
    borne_emplacements_response = admin_client.get(reverse("api-admin-emplacements"), {"borne": str(borne.id_borne)})

    assert bornes_response.status_code == status.HTTP_200_OK
    assert [item["id_borne"] for item in bornes_response.data["results"]] == [str(borne.id_borne)]
    assert str(other_borne.id_borne) not in [item["id_borne"] for item in bornes_response.data["results"]]

    assert emplacements_response.status_code == status.HTTP_200_OK
    assert {item["id_emplacement"] for item in emplacements_response.data["results"]} == {
        str(emplacement.id_emplacement) for emplacement in emplacements
    }
    assert str(other_emplacement.id_emplacement) not in {
        item["id_emplacement"] for item in emplacements_response.data["results"]
    }

    assert borne_emplacements_response.status_code == status.HTTP_200_OK
    assert {str(item["borne"]) for item in borne_emplacements_response.data["results"]} == {str(borne.id_borne)}


@pytest.mark.django_db
def test_admin_station_create_rejects_invalid_status(admin_client):
    response = admin_client.post(
        reverse("api-admin-stations"),
        {
            "nom": "Station Invalide",
            "localisation_text": "Quartier Nord",
            "latitude": 48.9,
            "longitude": 2.4,
            "statut": "ouverte",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "statut" in response.data


@pytest.mark.django_db
def test_admin_can_crud_emplacement(admin_client, station, borne):
    create_response = admin_client.post(
        reverse("api-admin-emplacements"),
        {
            "station": str(station.id_station),
            "borne": str(borne.id_borne),
            "numero": 1,
            "statut": "disponible",
            "lock_state": "verrouille",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    emplacement_id = create_response.data["id_emplacement"]
    assert create_response.data["borne_nom"] == "Borne 1"

    patch_response = admin_client.patch(
        reverse("api-admin-emplacement-detail", kwargs={"emplacement_id": emplacement_id}),
        {"statut": "maintenance"},
        format="json",
    )

    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["statut"] == "maintenance"

    delete_response = admin_client.delete(
        reverse("api-admin-emplacement-detail", kwargs={"emplacement_id": emplacement_id})
    )

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not Emplacement.objects.filter(id_emplacement=emplacement_id).exists()


@pytest.mark.django_db
def test_admin_emplacement_create_rejects_invalid_lock_state(admin_client, station):
    response = admin_client.post(
        reverse("api-admin-emplacements"),
        {
            "station": str(station.id_station),
            "numero": 7,
            "statut": "disponible",
            "lock_state": "ouvert",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "lock_state" in response.data


@pytest.mark.django_db
def test_admin_maintenance_create_rejects_invalid_status(admin_client, station, admin_user):
    technicien = Technicien.objects.create(
        utilisateur=admin_user,
        nom="Tech Admin",
        email="tech-admin@example.com",
        telephone="",
    )
    response = admin_client.post(
        reverse("api-admin-maintenances"),
        {
            "station": str(station.id_station),
            "technicien": str(technicien.id_technicien),
            "type": "Controle",
            "description": "Controle periodique",
            "status": "done",
            "date_planifiee": timezone.now().isoformat(),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "status" in response.data
    assert Maintenance.objects.count() == 0


@pytest.mark.django_db
def test_non_staff_cannot_create_station(authenticated_client):
    response = authenticated_client.post(
        reverse("api-admin-stations"),
        {
            "nom": "Forbidden",
            "localisation_text": "Forbidden",
            "latitude": 48.0,
            "longitude": 2.0,
            "statut": "active",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
