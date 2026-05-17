import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0018_device_last_command_ack"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceCommandLog",
            fields=[
                ("id_command", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("command_id", models.CharField(blank=True, default="", max_length=100)),
                ("action", models.CharField(blank=True, default="", max_length=20)),
                ("status", models.CharField(blank=True, default="", max_length=50)),
                ("message", models.CharField(blank=True, default="", max_length=255)),
                ("source", models.CharField(blank=True, default="", max_length=50)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("timestamp", models.DateTimeField(default=timezone.now)),
                (
                    "device",
                    models.ForeignKey(
                        db_column="id_device",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="command_logs",
                        to="api.device",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        db_column="id_session",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="device_command_logs",
                        to="api.session",
                    ),
                ),
            ],
            options={
                "db_table": "device_command_log",
            },
        ),
        migrations.AddIndex(
            model_name="devicecommandlog",
            index=models.Index(fields=["device", "timestamp"], name="idx_cmd_device_time"),
        ),
        migrations.AddIndex(
            model_name="devicecommandlog",
            index=models.Index(fields=["command_id"], name="idx_cmd_command_id"),
        ),
        migrations.AddIndex(
            model_name="devicecommandlog",
            index=models.Index(fields=["action", "timestamp"], name="idx_cmd_action_time"),
        ),
        migrations.AddIndex(
            model_name="devicecommandlog",
            index=models.Index(fields=["status", "timestamp"], name="idx_cmd_status_time"),
        ),
    ]
