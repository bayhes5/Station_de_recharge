from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0017_alter_reservation_auth_choice"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="last_command_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="device",
            name="last_command_action",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="device",
            name="last_command_status",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="device",
            name="last_command_message",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="device",
            name="last_command_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="device",
            index=models.Index(fields=["last_command_at"], name="idx_device_last_cmd_at"),
        ),
    ]
