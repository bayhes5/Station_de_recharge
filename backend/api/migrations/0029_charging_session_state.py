import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0028_alert_technician_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="charge_state",
            field=models.CharField(
                choices=[
                    ("reserved", "Réservée"),
                    ("access_validated", "Accès validé"),
                    ("waiting_plug", "En attente de branchement"),
                    ("charging", "Charge en cours"),
                    ("stopping", "Arrêt en cours"),
                    ("stopped", "Arrêtée"),
                    ("error", "Erreur"),
                ],
                default="reserved",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="charge_state_updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddIndex(
            model_name="session",
            index=models.Index(
                fields=["charge_state", "end_time"],
                name="idx_session_charge_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="session",
            constraint=models.CheckConstraint(
                condition=Q(
                    charge_state__in=[
                        "reserved",
                        "access_validated",
                        "waiting_plug",
                        "charging",
                        "stopping",
                        "stopped",
                        "error",
                    ]
                ),
                name="chk_session_charge_state",
            ),
        ),
    ]
