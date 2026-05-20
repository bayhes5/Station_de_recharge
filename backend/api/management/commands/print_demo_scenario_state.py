from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from api.models import CapteurData, Reservation, Session


class Command(BaseCommand):
    """Print the final state of one demo reservation as JSON."""

    help = "Print reservation/session/telemetry state for a demo reservation."

    def add_arguments(self, parser):
        """Declare command-line arguments."""
        parser.add_argument("--reference", required=True)

    def handle(self, *args, **options):
        """Fetch the reservation state and print a JSON summary."""
        reference = options["reference"].strip().upper()
        reservation = (
            Reservation.objects.select_related(
                "emplacement",
                "emplacement__station",
                "emplacement__borne",
                "emplacement__device",
            )
            .filter(reference_code=reference)
            .first()
        )
        if reservation is None:
            raise CommandError(f"Réservation {reference} introuvable.")

        session = (
            Session.objects.filter(reservation=reservation)
            .order_by("-start_time")
            .first()
        )
        device = getattr(reservation.emplacement, "device", None)
        slot_id = (
            device.slot_id or device.mac_address
            if device and (device.slot_id or device.mac_address)
            else f"slot{reservation.emplacement.numero}"
        )
        result = {
            "reservation": {
                "id": str(reservation.id_reservation),
                "reference_code": reservation.reference_code,
                "statut": reservation.statut,
                "auth_choice": reservation.auth_choice,
            },
            "terminal": {
                "station_id": str(reservation.emplacement.station_id),
                "station": reservation.emplacement.station.nom,
                "borne_id": str(reservation.emplacement.borne_id),
                "borne": reservation.emplacement.borne.nom,
                "mqtt_prefix": reservation.emplacement.borne.mqtt_prefix,
                "emplacement": reservation.emplacement.numero,
                "slot_id": slot_id,
            },
            "session": None,
            "device": None,
        }
        if session:
            result["session"] = {
                "id": str(session.id_session),
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "status": "closed" if session.end_time else "active",
                "telemetry_points": session.telemetries.count(),
            }
        if device:
            sensor_queryset = CapteurData.objects.filter(capteur__device=device)
            if session:
                sensor_queryset = sensor_queryset.filter(timestamp__gte=session.start_time)
                if session.end_time:
                    sensor_queryset = sensor_queryset.filter(timestamp__lte=session.end_time)
            result["device"] = {
                "slot_id": device.slot_id,
                "hardware_mac": device.hardware_mac,
                "mac_address": device.mac_address,
                "status": device.status,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "sensor_samples": sensor_queryset.count(),
            }
        self.stdout.write(json.dumps(result, ensure_ascii=False))
