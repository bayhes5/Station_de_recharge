from __future__ import annotations

import io
import json
import os
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.models import Authentification, Borne, Emplacement, Reservation, Utilisateur
from api.views import _create_temporary_auth


class Command(BaseCommand):
    """Create a deterministic QR reservation for local end-to-end demos."""

    help = "Prepare one QR reservation usable by the mobile/kiosk demo scenario."

    def add_arguments(self, parser):
        """Declare command-line arguments."""
        parser.add_argument("--reference", default="DEMOQR1")
        parser.add_argument("--pseudo", default="client_demo")
        parser.add_argument("--email", default="client.demo@station.local")
        parser.add_argument("--password", default="Client123!")
        parser.add_argument("--emplacement", type=int, default=1)
        parser.add_argument("--duration-minutes", type=int, default=60)
        parser.add_argument("--start-offset-minutes", type=int, default=-1)

    def handle(self, *args, **options):
        """Create the demo data and print a machine-readable JSON payload."""
        reference = options["reference"].strip().upper()
        if not reference:
            raise CommandError("La reference ne peut pas etre vide.")
        if options["duration_minutes"] <= 0:
            raise CommandError("--duration-minutes doit etre strictement positif.")

        call_command("bootstrap_demo_data", stdout=io.StringIO())
        station_name = os.environ.get("DEMO_STATION_NAME", "Station Demo")
        borne = (
            Borne.objects.select_related("station")
            .filter(station__nom=station_name, numero=1)
            .order_by("created_at")
            .first()
        )
        if borne is None:
            raise CommandError("Borne de demonstration introuvable.")

        emplacement = (
            Emplacement.objects.select_related("station", "borne", "device")
            .filter(borne=borne, numero=options["emplacement"])
            .first()
        )
        if emplacement is None:
            raise CommandError(f"Emplacement {options['emplacement']} introuvable.")

        now = timezone.now()
        date_debut = now + timedelta(minutes=options["start_offset_minutes"])
        date_fin = date_debut + timedelta(minutes=options["duration_minutes"])

        with transaction.atomic():
            user, _created = Utilisateur.objects.get_or_create(
                pseudo=options["pseudo"],
                defaults={
                    "email": options["email"],
                    "statut": "actif",
                },
            )
            user.email = options["email"]
            user.statut = "actif"
            user.set_password(options["password"])
            user.save()

            old_auth_ids = list(
                Reservation.objects.filter(reference_code=reference)
                .exclude(authentification__isnull=True)
                .values_list("authentification_id", flat=True)
            )
            Reservation.objects.filter(reference_code=reference).delete()
            for auth_id in old_auth_ids:
                if not Reservation.objects.filter(authentification_id=auth_id).exists():
                    Authentification.objects.filter(id_auth=auth_id).delete()

            auth_method, qr_payload = _create_temporary_auth(user, "qr", date_fin, reference)
            reservation = Reservation.objects.create(
                utilisateur=user,
                emplacement=emplacement,
                authentification=auth_method,
                auth_choice="qr",
                reference_code=reference,
                date_debut=date_debut,
                date_fin=date_fin,
                statut="confirmee",
            )

        device = getattr(emplacement, "device", None)
        result = {
            "user": {
                "pseudo": user.pseudo,
                "email": user.email,
                "password": options["password"],
            },
            "reservation": {
                "id": str(reservation.id_reservation),
                "reference_code": reservation.reference_code,
                "date_debut": reservation.date_debut.isoformat(),
                "date_fin": reservation.date_fin.isoformat(),
                "auth_choice": reservation.auth_choice,
                "qr_payload": qr_payload,
            },
            "terminal": {
                "station_id": str(emplacement.station_id),
                "station": emplacement.station.nom,
                "borne_id": str(emplacement.borne_id),
                "borne": emplacement.borne.nom,
                "borne_numero": emplacement.borne.numero,
                "mqtt_prefix": emplacement.borne.mqtt_prefix,
                "emplacement": emplacement.numero,
                "slot_id": device.mac_address if device and device.mac_address else f"slot{emplacement.numero}",
            },
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False))
