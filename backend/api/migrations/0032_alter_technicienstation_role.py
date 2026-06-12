from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0031_borne_terminal_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="technicienstation",
            name="role",
            field=models.CharField(
                choices=[
                    ("referent", "Référent"),
                    ("intervenant", "Intervenant"),
                    ("observateur", "Observateur"),
                ],
                default="intervenant",
                max_length=50,
            ),
        ),
    ]
