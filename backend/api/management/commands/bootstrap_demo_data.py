import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import Emplacement, Maintenance, ProfilUtilisateur, Station, Technicien, Utilisateur


class Command(BaseCommand):
    help = "Create demo station, emplacement, technician and maintenance for local development."

    def handle(self, *args, **options):
        station_name = os.environ.get("DEMO_STATION_NAME", "Station Demo")
        location_text = os.environ.get("DEMO_STATION_LOCATION", "Centre-ville")
        latitude = float(os.environ.get("DEMO_STATION_LATITUDE", "48.8566"))
        longitude = float(os.environ.get("DEMO_STATION_LONGITUDE", "2.3522"))
        station_status = os.environ.get("DEMO_STATION_STATUS", "active")
        emplacements_count = int(os.environ.get("DEMO_EMPLACEMENTS_COUNT", "2"))

        tech_pseudo = os.environ.get("DEMO_TECH_PSEUDO", "tech")
        tech_email = os.environ.get("DEMO_TECH_EMAIL", "tech@station.local")
        tech_password = os.environ.get("DEMO_TECH_PASSWORD", "Tech123!")
        tech_name = os.environ.get("DEMO_TECH_NAME", "Technicien Demo")
        tech_phone = os.environ.get("DEMO_TECH_PHONE", "0600000000")

        station, _ = Station.objects.get_or_create(
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
        station.save()

        for numero in range(1, emplacements_count + 1):
            emplacement, _ = Emplacement.objects.get_or_create(
                station=station,
                numero=numero,
                defaults={
                    "statut": "disponible",
                    "lock_state": "verrouille",
                },
            )
            emplacement.statut = "disponible"
            emplacement.lock_state = "verrouille"
            emplacement.save()

        user = Utilisateur.objects.filter(pseudo=tech_pseudo).first()
        if user is None:
            user = Utilisateur.objects.create_user(
                pseudo=tech_pseudo,
                email=tech_email,
                password=tech_password,
                statut="actif",
            )
        else:
            user.email = tech_email
            user.statut = "actif"
            user.set_password(tech_password)
            user.save()

        profile, _ = ProfilUtilisateur.objects.get_or_create(
            utilisateur=user,
            defaults={"nom": tech_name, "telephone": tech_phone},
        )
        profile.nom = tech_name
        profile.telephone = tech_phone
        profile.save(update_fields=["nom", "telephone"])

        technician, _ = Technicien.objects.get_or_create(
            utilisateur=user,
            defaults={
                "nom": tech_name,
                "email": tech_email,
                "telephone": tech_phone,
            },
        )
        technician.nom = tech_name
        technician.email = tech_email
        technician.telephone = tech_phone
        technician.utilisateur = user
        technician.save()

        first_emplacement = station.emplacements.order_by("numero").first()
        if first_emplacement:
            maintenance, _ = Maintenance.objects.get_or_create(
                station=station,
                technicien=technician,
                type="Contrôle préventif",
                defaults={
                    "description": "Maintenance de démonstration créée automatiquement.",
                    "status": "planifiee",
                    "date_planifiee": timezone.now() + timedelta(days=1),
                },
            )
            maintenance.description = "Maintenance de démonstration créée automatiquement."
            maintenance.status = "planifiee"
            maintenance.date_planifiee = timezone.now() + timedelta(days=1)
            maintenance.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: station={station.nom}, emplacements={emplacements_count}, technicien={technician.nom}"
            )
        )
