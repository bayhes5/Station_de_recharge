import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def create_default_bornes(apps, schema_editor):
    Station = apps.get_model("api", "Station")
    Borne = apps.get_model("api", "Borne")
    Emplacement = apps.get_model("api", "Emplacement")

    for station in Station.objects.all():
        borne, _created = Borne.objects.get_or_create(
            station=station,
            numero=1,
            defaults={
                "nom": "Borne 1",
                "statut": "active",
                "created_at": timezone.now(),
            },
        )
        Emplacement.objects.filter(station=station, borne__isnull=True).update(borne=borne)


def remove_default_bornes(apps, schema_editor):
    Borne = apps.get_model("api", "Borne")
    Borne.objects.filter(numero=1, nom="Borne 1").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0015_enable_timescaledb_extension"),
    ]

    operations = [
        migrations.CreateModel(
            name="Borne",
            fields=[
                ("id_borne", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("numero", models.PositiveIntegerField()),
                ("nom", models.CharField(max_length=100)),
                ("mqtt_prefix", models.CharField(blank=True, default="", max_length=120)),
                ("statut", models.CharField(choices=[("active", "Active"), ("maintenance", "Maintenance"), ("inactive", "Inactive")], default="active", max_length=50)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("station", models.ForeignKey(db_column="id_station", on_delete=django.db.models.deletion.CASCADE, related_name="bornes", to="api.station")),
            ],
            options={
                "db_table": "borne",
                "unique_together": {("station", "numero")},
            },
        ),
        migrations.AddIndex(
            model_name="borne",
            index=models.Index(fields=["station", "statut"], name="idx_borne_station_statut"),
        ),
        migrations.AddIndex(
            model_name="borne",
            index=models.Index(fields=["mqtt_prefix"], name="idx_borne_mqtt_prefix"),
        ),
        migrations.AddConstraint(
            model_name="borne",
            constraint=models.CheckConstraint(condition=models.Q(("statut__in", ["active", "maintenance", "inactive"])), name="chk_borne_statut"),
        ),
        migrations.AddField(
            model_name="emplacement",
            name="borne",
            field=models.ForeignKey(blank=True, db_column="id_borne", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="emplacements", to="api.borne"),
        ),
        migrations.RunPython(create_default_bornes, remove_default_bornes),
        migrations.AlterField(
            model_name="emplacement",
            name="borne",
            field=models.ForeignKey(blank=True, db_column="id_borne", on_delete=django.db.models.deletion.CASCADE, related_name="emplacements", to="api.borne"),
        ),
        migrations.AlterUniqueTogether(
            name="emplacement",
            unique_together={("borne", "numero")},
        ),
        migrations.AddIndex(
            model_name="emplacement",
            index=models.Index(fields=["borne", "statut"], name="idx_emp_borne_statut"),
        ),
    ]
