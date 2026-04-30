import os

from django.core.management.base import BaseCommand

from api.models import Utilisateur


class Command(BaseCommand):
    """Create or refresh the default administrator from environment variables."""

    help = "Create or update the default Django superuser for local development."

    def handle(self, *args, **options):
        """Upsert the configured administrator account for local deployments."""
        pseudo = os.environ.get("ADMIN_PSEUDO", "admin")
        email = os.environ.get("ADMIN_EMAIL", "admin@station.local")
        password = os.environ.get("ADMIN_PASSWORD", "Admin123!")

        if not password:
            self.stdout.write(self.style.WARNING("ADMIN_PASSWORD is empty, skipping superuser bootstrap."))
            return

        user, created = Utilisateur.objects.get_or_create(
            pseudo=pseudo,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        message = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Default superuser {message}: pseudo={user.pseudo}, email={user.email}"
            )
        )
