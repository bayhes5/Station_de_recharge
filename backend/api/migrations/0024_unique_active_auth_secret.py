from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def deactivate_duplicate_active_secrets(apps, _schema_editor):
    """Keep the newest active credential before adding the unique constraint."""
    auth_model = apps.get_model("api", "Authentification")
    seen = set()
    now = timezone.now()
    queryset = (
        auth_model.objects.filter(is_active=True)
        .exclude(hash_valeur="pending")
        .order_by("type_auth_id", "hash_valeur", "-created_at", "-id_auth")
    )

    for auth_method in queryset:
        key = (auth_method.type_auth_id, auth_method.hash_valeur)
        if key not in seen:
            seen.add(key)
            continue

        metadata = auth_method.metadata or {}
        metadata.update(
            {
                "revoked_at": now.isoformat(),
                "revocation_source": "duplicate_active_secret_migration",
            }
        )
        auth_method.is_active = False
        auth_method.expiration = now
        auth_method.metadata = metadata
        auth_method.save(update_fields=["is_active", "expiration", "metadata"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0023_device_slot_identity"),
    ]

    operations = [
        migrations.RunPython(deactivate_duplicate_active_secrets, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="authentification",
            constraint=models.UniqueConstraint(
                fields=("type_auth", "hash_valeur"),
                condition=Q(is_active=True) & ~Q(hash_valeur="pending"),
                name="uniq_active_auth_type_secret",
            ),
        ),
    ]
