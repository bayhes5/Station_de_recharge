from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0016_borne_emplacement_borne"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="auth_choice",
            field=models.CharField(
                choices=[
                    ("rfid", "RFID"),
                    ("qr", "QR code"),
                    ("code", "Code SMS temporaire"),
                ],
                default="qr",
                max_length=20,
            ),
        ),
    ]
