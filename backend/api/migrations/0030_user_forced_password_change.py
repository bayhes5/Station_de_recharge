from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0029_charging_session_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="utilisateur",
            name="password_reset_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
