# Generated manually to keep the clear authentication value for profile/history views.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_reservation_reference_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="authentification",
            name="display_value",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
