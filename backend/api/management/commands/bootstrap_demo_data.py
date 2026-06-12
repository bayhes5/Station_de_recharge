from __future__ import annotations

import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import (
    Alerte,
    Authentification,
    Borne,
    BorneStatus,
    CapteurData,
    Device,
    DeviceCommandLog,
    DeviceStatus,
    DeviceType,
    Emplacement,
    EmplacementStatus,
    FirmwareUpdateStatus,
    LockState,
    Maintenance,
    MaintenanceStatus,
    ProfilUtilisateur,
    Reservation,
    Station,
    StationStatus,
    Technicien,
    TechnicienStation,
    TechnicianStationRole,
    Utilisateur,
    UserStatus,
)


LEGACY_DEMO_RESERVATION_CODES = {
    "DEMOWAIT1",
    "DEMOCHG1",
    "DEMOFUT1",
    "DEMORFID1",
    "DEMOSMS1",
    "DEMODONE1",
    "DEMODONE2",
    "DEMOCAN1",
}
LEGACY_DEMO_USERS = {
    "demo_alice",
    "demo_mehdi",
    "demo_clara",
    "demo_noah",
    "tech_gare",
    "tech_universite",
}
LEGACY_DEMO_STATIONS = {"Station Démo Gare", "Station Démo Université"}
LEGACY_DEMO_TECH_EMAILS = {
    "tech.gare@station.local",
    "tech.universite@station.local",
}


class Command(BaseCommand):
    """Seed a minimal and deterministic prototype environment."""

    help = "Create one demo station, one borne, three emplacements, ESP32 placeholders and one technician."

    def handle(self, *args, **options):
        """Create or update deterministic demo records from environment values."""
        with transaction.atomic():
            self._cleanup_legacy_realistic_seed()
            admin = self._ensure_admin()
            station, borne, emplacements = self._ensure_infrastructure()
            technician = self._ensure_technician(station)
            self._ensure_maintenance(station, technician)

        admin_label = admin.pseudo if admin else "skipped"
        self.stdout.write(
            self.style.SUCCESS(
                "Demo data ready: "
                f"admin={admin_label}, "
                f"station={station.nom}, "
                f"borne={borne.nom}, "
                f"emplacements={len(emplacements)}, "
                f"technicien={technician.nom}"
            )
        )

    def _cleanup_legacy_realistic_seed(self):
        """Remove previous synthetic demo activity while preserving user tests."""
        Alerte.objects.filter(message__startswith="[Démo]").delete()
        DeviceCommandLog.objects.filter(command_id__startswith="demo-").delete()
        CapteurData.objects.filter(capteur__device__emplacement__station__nom__in=LEGACY_DEMO_STATIONS).delete()
        Reservation.objects.filter(reference_code__in=LEGACY_DEMO_RESERVATION_CODES).delete()
        Authentification.objects.filter(metadata__demo_seed="realistic").delete()
        Station.objects.filter(nom__in=LEGACY_DEMO_STATIONS).delete()
        Technicien.objects.filter(email__in=LEGACY_DEMO_TECH_EMAILS).delete()
        Utilisateur.objects.filter(pseudo__in=LEGACY_DEMO_USERS).delete()

    def _ensure_admin(self):
        """Create or refresh the deterministic administrator account."""
        pseudo = os.environ.get("ADMIN_PSEUDO", "admin")
        email = os.environ.get("ADMIN_EMAIL", "admin@station.local")
        password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
        name = os.environ.get("ADMIN_NAME", "Administrateur")
        phone = os.environ.get("ADMIN_PHONE", "")

        if not password:
            return None

        user, _created = Utilisateur.objects.get_or_create(
            pseudo=pseudo,
            defaults={
                "email": email,
                "statut": UserStatus.ACTIVE,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        user.email = email
        user.statut = UserStatus.ACTIVE
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save(
            update_fields=[
                "email",
                "statut",
                "is_staff",
                "is_superuser",
                "is_active",
                "password",
            ]
        )

        profile, _created = ProfilUtilisateur.objects.get_or_create(
            utilisateur=user,
            defaults={"nom": name, "telephone": phone},
        )
        profile.nom = name
        profile.telephone = phone
        profile.save(update_fields=["nom", "telephone"])
        return user

    def _ensure_infrastructure(self):
        """Create or refresh the prototype station, cabinet and slots."""
        station_name = os.environ.get("DEMO_STATION_NAME", "Station Demo")
        location_text = os.environ.get("DEMO_STATION_LOCATION", "Centre-ville")
        latitude = float(os.environ.get("DEMO_STATION_LATITUDE", "48.8566"))
        longitude = float(os.environ.get("DEMO_STATION_LONGITUDE", "2.3522"))
        station_status = os.environ.get("DEMO_STATION_STATUS", StationStatus.ACTIVE)
        emplacements_count = int(os.environ.get("DEMO_EMPLACEMENTS_COUNT", "3"))
        firmware_version = os.environ.get("DEMO_ESP32_FIRMWARE_VERSION", "prototype")

        station, _created = Station.objects.get_or_create(
            nom=station_name,
            defaults={
                "localisation_text": location_text,
                "latitude": latitude,
                "longitude": longitude,
                "statut": station_status,
            },
        )
        station.localisation_text = location_text
        station.latitude = latitude
        station.longitude = longitude
        station.statut = station_status
        station.save(update_fields=["localisation_text", "latitude", "longitude", "statut"])

        borne, _created = Borne.objects.get_or_create(
            station=station,
            numero=1,
            defaults={
                "nom": os.environ.get("DEMO_BORNE_NAME", "Borne 1"),
                "terminal_code": os.environ.get("DEMO_TERMINAL_CODE", "station-demo-borne-1"),
                "mqtt_prefix": os.environ.get("DEMO_BORNE_MQTT_PREFIX", "station-demo/borne-1"),
                "statut": os.environ.get("DEMO_BORNE_STATUS", BorneStatus.ACTIVE),
            },
        )
        borne.nom = os.environ.get("DEMO_BORNE_NAME", "Borne 1")
        borne.terminal_code = os.environ.get("DEMO_TERMINAL_CODE", "station-demo-borne-1")
        borne.mqtt_prefix = os.environ.get("DEMO_BORNE_MQTT_PREFIX", "station-demo/borne-1")
        borne.statut = os.environ.get("DEMO_BORNE_STATUS", BorneStatus.ACTIVE)
        borne.save(update_fields=["nom", "terminal_code", "mqtt_prefix", "statut"])

        emplacements = []
        for numero in range(1, emplacements_count + 1):
            emplacement, _created = Emplacement.objects.get_or_create(
                borne=borne,
                numero=numero,
                defaults={
                    "station": station,
                    "statut": EmplacementStatus.AVAILABLE,
                    "lock_state": LockState.LOCKED,
                },
            )
            emplacement.statut = EmplacementStatus.AVAILABLE
            emplacement.lock_state = LockState.LOCKED
            emplacement.save(update_fields=["station", "borne", "statut", "lock_state"])

            self._ensure_device(emplacement, numero, firmware_version)
            emplacements.append(emplacement)

        return station, borne, emplacements

    def _ensure_device(self, emplacement, numero, firmware_version):
        """Create or reset one ESP32 placeholder for a demo slot."""
        device, _created = Device.objects.get_or_create(
            emplacement=emplacement,
            defaults={
                "type_device": DeviceType.ESP32,
                "firmware_version": firmware_version,
                "expected_firmware_version": "",
                "firmware_update_status": FirmwareUpdateStatus.UNKNOWN,
                "status": DeviceStatus.PROVISIONED,
            },
        )
        device.type_device = DeviceType.ESP32
        device.firmware_version = firmware_version
        device.expected_firmware_version = ""
        device.firmware_update_status = FirmwareUpdateStatus.UNKNOWN
        device.slot_id = f"slot{numero}"
        device.mac_address = ""
        device.hardware_mac = ""
        device.ip_address = None
        device.last_seen = None
        device.status = DeviceStatus.PROVISIONED
        device.last_command_id = ""
        device.last_command_action = ""
        device.last_command_status = ""
        device.last_command_message = ""
        device.last_command_at = None
        device.save()
        return device

    def _ensure_technician(self, station):
        """Create or refresh the demo technician and station assignment."""
        pseudo = os.environ.get("DEMO_TECH_PSEUDO", "tech")
        email = os.environ.get("DEMO_TECH_EMAIL", "tech@station.local")
        password = os.environ.get("DEMO_TECH_PASSWORD", "Tech123!")
        name = os.environ.get("DEMO_TECH_NAME", "Technicien Demo")
        phone = os.environ.get("DEMO_TECH_PHONE", "0600000000")

        user = Utilisateur.objects.filter(pseudo=pseudo).first()
        if user is None:
            user = Utilisateur.objects.create_user(
                pseudo=pseudo,
                email=email,
                password=password,
                statut=UserStatus.ACTIVE,
            )
        else:
            user.email = email
            user.statut = UserStatus.ACTIVE
            user.is_active = True
            user.set_password(password)
            user.save(update_fields=["email", "statut", "is_active", "password"])

        profile, _created = ProfilUtilisateur.objects.get_or_create(
            utilisateur=user,
            defaults={"nom": name, "telephone": phone},
        )
        profile.nom = name
        profile.telephone = phone
        profile.save(update_fields=["nom", "telephone"])

        technician, _created = Technicien.objects.get_or_create(
            email=email,
            defaults={
                "utilisateur": user,
                "nom": name,
                "telephone": phone,
            },
        )
        technician.utilisateur = user
        technician.nom = name
        technician.telephone = phone
        technician.save(update_fields=["utilisateur", "nom", "telephone"])

        TechnicienStation.objects.update_or_create(
            technicien=technician,
            station=station,
            defaults={
                "role": TechnicianStationRole.REFERENT,
                "is_active": True,
            },
        )
        return technician

    def _ensure_maintenance(self, station, technician):
        """Create or refresh a planned maintenance item for the demo station."""
        Maintenance.objects.update_or_create(
            station=station,
            technicien=technician,
            type="Contrôle préventif",
            defaults={
                "description": "Maintenance de démonstration créée automatiquement.",
                "status": MaintenanceStatus.PLANNED,
                "date_planifiee": timezone.now() + timedelta(days=1),
                "date_realisee": None,
            },
        )
