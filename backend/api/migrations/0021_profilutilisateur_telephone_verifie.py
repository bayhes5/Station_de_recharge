from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0020_technicien_station"),
    ]

    operations = [
        migrations.AddField(
            model_name="profilutilisateur",
            name="telephone_verifie",
            field=models.BooleanField(default=False),
        ),
    ]
