from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.models import Session
from api.services.mqtt_simulator import SCENARIOS, build_telemetry_payload, telemetry_topic


class Command(BaseCommand):
    """Publish simulated ESP32 telemetry to the configured MQTT broker."""

    help = "Publish local MQTT telemetry for supervision tests without ESP32 or Wokwi."

    def add_arguments(self, parser):
        """Declare simulator command-line arguments."""
        parser.add_argument(
            "--slots",
            nargs="+",
            default=["slot1", "slot2", "slot3"],
            help="Slot identifiers to simulate.",
        )
        parser.add_argument(
            "--scenario",
            choices=SCENARIOS,
            default="normal",
            help="Telemetry scenario to publish.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=2.0,
            help="Delay in seconds between two telemetry batches.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=0,
            help="Number of batches to publish. Use 0 for an infinite stream.",
        )
        parser.add_argument("--session-id", default="simulation")
        parser.add_argument(
            "--active-session",
            action="store_true",
            help="Simulate only the latest active charging session and its assigned slot.",
        )
        parser.add_argument(
            "--reservation-code",
            default="",
            help="Restrict --active-session to one reservation reference code.",
        )
        parser.add_argument(
            "--topic-prefix",
            default="",
            help="Optional station/borne MQTT prefix, for example station-centre/borne-1.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        """Start the MQTT telemetry simulator."""
        if not options["slots"]:
            raise CommandError("Au moins un slot doit etre fourni.")
        if options["interval"] <= 0:
            raise CommandError("L'intervalle doit etre strictement positif.")
        if options["count"] < 0:
            raise CommandError("Le nombre de lots doit etre positif ou nul.")
        if options["reservation_code"]:
            options["active_session"] = True
        if options["active_session"]:
            session = self._resolve_active_session(options["reservation_code"])
            slot_id = self._slot_id_for_session(session)
            options["slots"] = [slot_id]
            options["session_id"] = str(session.id_session)
            if not options["topic_prefix"]:
                options["topic_prefix"] = session.emplacement.borne.mqtt_prefix
            self.stdout.write(
                self.style.SUCCESS(
                    "Simulation liee a la session active: "
                    f"reservation={session.reservation.reference_code} "
                    f"emplacement={session.emplacement.numero} slot={slot_id}"
                )
            )

        client = None if options["dry_run"] else self._connect_client()
        started_at = datetime.now(timezone.utc)
        tick = 0

        self.stdout.write(
            self.style.SUCCESS(
                "Simulation MQTT demarree: "
                f"slots={','.join(options['slots'])} scenario={options['scenario']}"
            )
        )

        try:
            while options["count"] == 0 or tick < options["count"]:
                elapsed_seconds = tick * options["interval"]
                self._publish_batch(client, options, started_at, elapsed_seconds)
                tick += 1
                if options["count"] == 0 or tick < options["count"]:
                    time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Simulation MQTT arretee."))
        finally:
            if client is not None:
                client.loop_stop()
                client.disconnect()

    def _connect_client(self):
        """Connect a paho MQTT client from Django settings."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise CommandError("Installe paho-mqtt pour lancer le simulateur MQTT.") from exc

        client = mqtt.Client(client_id=f"{settings.MQTT_BACKEND_CLIENT_ID}-simulator")
        if settings.MQTT_USERNAME:
            client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
        if settings.MQTT_TLS_ENABLED:
            client.tls_set()
        client.connect(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
        client.loop_start()
        return client

    def _resolve_active_session(self, reservation_code: str):
        """Return the charging session that should drive the local simulator."""
        queryset = Session.objects.select_related(
            "reservation",
            "emplacement",
            "emplacement__borne",
            "emplacement__device",
        ).filter(end_time__isnull=True)
        if reservation_code:
            queryset = queryset.filter(reservation__reference_code__iexact=reservation_code.strip())
        session = queryset.order_by("-start_time").first()
        if session is None:
            detail = f" pour la reservation {reservation_code}" if reservation_code else ""
            raise CommandError(f"Aucune session de charge active{detail}.")
        return session

    def _slot_id_for_session(self, session):
        """Return the MQTT slot identifier assigned to a charging session."""
        device = getattr(session.emplacement, "device", None)
        if device and device.mac_address:
            return device.mac_address
        return f"slot{session.emplacement.numero}"

    def _publish_batch(self, client, options, started_at: datetime, elapsed_seconds: float):
        """Publish one telemetry sample for each requested slot."""
        for index, slot_id in enumerate(options["slots"]):
            payload = build_telemetry_payload(
                slot_id=slot_id,
                tick=int(elapsed_seconds) + index,
                scenario=options["scenario"],
                session_id=options["session_id"],
                started_at=started_at,
            )
            topic = telemetry_topic(
                settings.MQTT_BASE_TOPIC,
                slot_id,
                options["topic_prefix"],
            )
            payload_text = json.dumps(payload)

            if client is None:
                self.stdout.write(f"{topic} {payload_text}")
                continue

            result = client.publish(topic, payload_text, qos=settings.MQTT_QOS)
            result.wait_for_publish(timeout=2)
            self.stdout.write(f"publie {topic}: {payload_text}")
