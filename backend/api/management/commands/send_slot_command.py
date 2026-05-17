from django.core.management.base import BaseCommand, CommandError

from api.services.mqtt_commands import publish_slot_command


class Command(BaseCommand):
    """Publish a manual MQTT command to one ESP32 slot."""

    help = "Publish a START/STOP/LOCK/UNLOCK command to one ESP32 command topic."

    def add_arguments(self, parser):
        """Declare command-line arguments."""
        parser.add_argument("slot_id")
        parser.add_argument("action", choices=("START", "STOP", "LOCK", "UNLOCK"))
        parser.add_argument("--session-id", default="")
        parser.add_argument(
            "--topic-prefix",
            default=None,
            help="MQTT prefix before the slot id, for example station/<station_id>/<borne_id>.",
        )

    def handle(self, *args, **options):
        """Publish the requested command."""
        try:
            payload = publish_slot_command(
                options["slot_id"],
                options["action"],
                topic_prefix=options["topic_prefix"],
                session_id=options["session_id"],
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Commande MQTT envoyee: {payload}"))
