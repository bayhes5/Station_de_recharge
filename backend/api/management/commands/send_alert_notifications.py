from django.core.management.base import BaseCommand

from api.services.email_notifications import notify_pending_alerts


class Command(BaseCommand):
    """Send technician emails for active alerts matching the notification policy."""

    help = "Send technician email notifications for active alerts that match the configured policy."

    def handle(self, *args, **options):
        """Run one notification pass."""
        result = notify_pending_alerts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Alert notifications sent: alerts={result['alerts_notified']} emails={result['emails_sent']}"
            )
        )
