from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0024_unique_active_auth_secret"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="expected_firmware_version",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="device",
            name="firmware_update_status",
            field=models.CharField(
                choices=[
                    ("unknown", "Non renseigne"),
                    ("up_to_date", "A jour"),
                    ("update_required", "Mise a jour requise"),
                    ("update_scheduled", "Mise a jour planifiee"),
                    ("updating", "Mise a jour en cours"),
                    ("failed", "Echec de mise a jour"),
                ],
                default="unknown",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="device",
            name="ota_update_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="device",
            name="ota_target_version",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="device",
            name="ota_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="device",
            name="ota_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="device",
            name="ota_last_error",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddConstraint(
            model_name="device",
            constraint=models.CheckConstraint(
                condition=Q(
                    firmware_update_status__in=[
                        "unknown",
                        "up_to_date",
                        "update_required",
                        "update_scheduled",
                        "updating",
                        "failed",
                    ]
                ),
                name="chk_device_fw_status",
            ),
        ),
        migrations.AddIndex(
            model_name="device",
            index=models.Index(
                fields=["firmware_update_status"],
                name="idx_device_fw_status",
            ),
        ),
        migrations.AddIndex(
            model_name="device",
            index=models.Index(
                fields=["expected_firmware_version"],
                name="idx_device_fw_expected",
            ),
        ),
    ]
