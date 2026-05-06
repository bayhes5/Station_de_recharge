from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_delete_port"),
    ]

    operations = [
        migrations.AddField(
            model_name="authentification",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
