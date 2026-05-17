from django.db import migrations, models


def copy_legacy_mac_to_slot_id(apps, _schema_editor):
    """Move the legacy logical slot stored in mac_address to slot_id."""
    device_model = apps.get_model("api", "Device")
    for device in device_model.objects.all().only("id_device", "mac_address", "slot_id"):
        if not device.slot_id and device.mac_address:
            device.slot_id = device.mac_address
            device.save(update_fields=["slot_id"])


def copy_slot_id_to_legacy_mac(apps, _schema_editor):
    """Keep rollback data readable by the previous code path."""
    device_model = apps.get_model("api", "Device")
    for device in device_model.objects.all().only("id_device", "mac_address", "slot_id"):
        if not device.mac_address and device.slot_id:
            device.mac_address = device.slot_id
            device.save(update_fields=["mac_address"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0022_alert_notification_policy_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="slot_id",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="device",
            name="hardware_mac",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.RunPython(copy_legacy_mac_to_slot_id, copy_slot_id_to_legacy_mac),
        migrations.AddIndex(
            model_name="device",
            index=models.Index(fields=["slot_id"], name="idx_device_slot_id"),
        ),
        migrations.AddIndex(
            model_name="device",
            index=models.Index(fields=["hardware_mac"], name="idx_device_hw_mac"),
        ),
    ]
