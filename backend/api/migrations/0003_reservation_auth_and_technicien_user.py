# Generated manually to support reservation authentication choices and technician profiles.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_utilisateur_auth_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="auth_choice",
            field=models.CharField(default="qr", max_length=20),
        ),
        migrations.AddField(
            model_name="reservation",
            name="authentification",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reservations",
                to="api.authentification",
                db_column="id_auth",
            ),
        ),
        migrations.AddField(
            model_name="technicien",
            name="utilisateur",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="technicien_profile",
                to="api.utilisateur",
                db_column="id_user",
            ),
        ),
    ]
