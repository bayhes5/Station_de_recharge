from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0021_profilutilisateur_telephone_verifie"),
    ]

    operations = [
        migrations.AddField(
            model_name="alerte",
            name="first_seen",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="alerte",
            name="last_seen",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="alerte",
            name="notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="alerte",
            name="notification_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
