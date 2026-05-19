from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0027_optional_postgresql_anonymizer"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="alerte",
            name="chk_alert_status",
        ),
        migrations.AlterField(
            model_name="alerte",
            name="status",
            field=models.CharField(
                choices=[
                    ("nouvelle", "Nouvelle"),
                    ("active", "Active"),
                    ("prise_en_charge", "Prise en charge"),
                    ("resolue", "Résolue"),
                    ("closed", "Fermée"),
                    ("fermee", "Fermée"),
                ],
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="alerte",
            name="assigned_technician",
            field=models.ForeignKey(
                blank=True,
                db_column="assigned_technician_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_alerts",
                to="api.technicien",
            ),
        ),
        migrations.AddField(
            model_name="alerte",
            name="acknowledged_by",
            field=models.ForeignKey(
                blank=True,
                db_column="acknowledged_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="acknowledged_alerts",
                to="api.technicien",
            ),
        ),
        migrations.AddField(
            model_name="alerte",
            name="acknowledged_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="alerte",
            name="resolved_by",
            field=models.ForeignKey(
                blank=True,
                db_column="resolved_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resolved_alerts",
                to="api.technicien",
            ),
        ),
        migrations.AddField(
            model_name="alerte",
            name="resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="alerte",
            name="resolution_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddIndex(
            model_name="alerte",
            index=models.Index(
                fields=["assigned_technician", "status"],
                name="idx_alert_tech_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="alerte",
            constraint=models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "nouvelle",
                        "active",
                        "prise_en_charge",
                        "resolue",
                        "closed",
                        "fermee",
                    ]
                ),
                name="chk_alert_status",
            ),
        ),
    ]
