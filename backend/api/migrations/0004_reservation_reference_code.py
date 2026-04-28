# Generated manually to add a human-readable reservation reference code.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_reservation_auth_and_technicien_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="reference_code",
            field=models.CharField(blank=True, max_length=12, null=True, unique=True),
        ),
    ]
