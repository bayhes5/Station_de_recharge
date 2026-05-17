from django.core.management.base import BaseCommand

from api.services.operational_alerts import scan_session_telemetry_gaps


class Command(BaseCommand):
    """Create or resolve alerts for active sessions without recent telemetry."""

    help = "Scan active charging sessions and alert when telemetry is missing."

    def handle(self, *args, **options):
        """Run one session telemetry health pass."""
        result = scan_session_telemetry_gaps()
        self.stdout.write(
            self.style.SUCCESS(
                "Session telemetry health checked: "
                f"created={result.created} updated={result.updated} resolved={result.resolved}"
            )
        )
