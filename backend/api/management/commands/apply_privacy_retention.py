from django.core.management.base import BaseCommand

from api.services.retention import apply_privacy_retention


class Command(BaseCommand):
    """Apply the configured privacy retention policy."""

    help = "Apply RGPD retention rules for telemetry, logs, alerts and anonymized accounts."

    def handle(self, *args, **options):
        """Run the retention policy and print an operational summary."""
        result = apply_privacy_retention()
        if not result.enabled:
            self.stdout.write(self.style.WARNING("Privacy retention disabled."))
            return

        self.stdout.write(self.style.SUCCESS("Privacy retention applied."))
        self.stdout.write(f"Anonymized users: {result.anonymized_users}")
        for key, deleted_count in sorted(result.deleted.items()):
            cutoff = result.cutoffs.get(key)
            cutoff_label = cutoff.isoformat() if cutoff else "disabled"
            self.stdout.write(f"{key}: deleted={deleted_count} cutoff={cutoff_label}")
