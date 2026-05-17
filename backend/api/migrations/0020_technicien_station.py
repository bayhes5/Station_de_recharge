# Generated manually to scope technician access by station.

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0019_device_command_log"),
    ]

    operations = [
        migrations.CreateModel(
            name="TechnicienStation",
            fields=[
                (
                    "id_assignment",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("referent", "Referent"),
                            ("intervenant", "Intervenant"),
                            ("observateur", "Observateur"),
                        ],
                        default="intervenant",
                        max_length=50,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "station",
                    models.ForeignKey(
                        db_column="id_station",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="technician_assignments",
                        to="api.station",
                    ),
                ),
                (
                    "technicien",
                    models.ForeignKey(
                        db_column="id_technicien",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="station_assignments",
                        to="api.technicien",
                    ),
                ),
            ],
            options={
                "db_table": "technicien_station",
            },
        ),
        migrations.AddConstraint(
            model_name="technicienstation",
            constraint=models.UniqueConstraint(
                fields=("technicien", "station"),
                name="uq_technicien_station",
            ),
        ),
        migrations.AddConstraint(
            model_name="technicienstation",
            constraint=models.CheckConstraint(
                condition=models.Q(("role__in", ["referent", "intervenant", "observateur"])),
                name="chk_tech_station_role",
            ),
        ),
        migrations.AddIndex(
            model_name="technicienstation",
            index=models.Index(
                fields=["technicien", "is_active"],
                name="idx_tech_station_tech",
            ),
        ),
        migrations.AddIndex(
            model_name="technicienstation",
            index=models.Index(
                fields=["station", "is_active"],
                name="idx_tech_station_station",
            ),
        ),
    ]
