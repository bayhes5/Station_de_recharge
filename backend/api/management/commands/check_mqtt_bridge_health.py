import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Check the local heartbeat written by the MQTT bridge process."""

    help = "Fail when the MQTT bridge heartbeat is missing or stale."

    def handle(self, *args, **options):
        """Validate that the MQTT bridge heartbeat file is fresh enough."""
        heartbeat_path = Path(settings.MQTT_BRIDGE_HEARTBEAT_FILE)
        max_age = settings.MQTT_BRIDGE_HEARTBEAT_MAX_AGE_SECONDS

        if not heartbeat_path.exists():
            raise CommandError(f"Heartbeat MQTT bridge absent: {heartbeat_path}")

        try:
            heartbeat_value = float(heartbeat_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            raise CommandError(f"Heartbeat MQTT bridge illisible: {heartbeat_path}") from exc

        age = time.time() - heartbeat_value
        if age > max_age:
            raise CommandError(f"Heartbeat MQTT bridge trop ancien: {age:.1f}s > {max_age}s")

        self.stdout.write(self.style.SUCCESS(f"MQTT bridge healthy: heartbeat age {age:.1f}s"))
