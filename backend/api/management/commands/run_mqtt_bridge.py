from django.core.management.base import BaseCommand

from api.mqtt import run_mqtt_bridge


class Command(BaseCommand):
    """Run the MQTT bridge that ingests ESP32 telemetry into the backend."""

    help = "Subscribe to ESP32 MQTT telemetry and enqueue persistence tasks."

    def handle(self, *args, **options):
        """Start the long-running MQTT bridge process."""
        self.stdout.write(self.style.SUCCESS("Bridge MQTT backend demarre."))
        run_mqtt_bridge()
