from django.db import migrations, models
from django.db.models import Q


def _fallback_terminal_code(borne):
    if borne.mqtt_prefix:
        return borne.mqtt_prefix.strip("/").replace("/", "-")[:120]
    station_name = (borne.station.nom if borne.station_id else "station").lower()
    normalized = "".join(char if char.isalnum() else "-" for char in station_name)
    normalized = "-".join(part for part in normalized.split("-") if part)
    return f"{normalized or 'station'}-borne-{borne.numero}"[:120]


def populate_terminal_codes(apps, _schema_editor):
    Borne = apps.get_model("api", "Borne")
    used_codes = set()
    for borne in Borne.objects.select_related("station").order_by("created_at", "id_borne"):
        base_code = _fallback_terminal_code(borne)
        code = base_code
        suffix = 2
        while code in used_codes or Borne.objects.exclude(pk=borne.pk).filter(terminal_code=code).exists():
            trimmed = base_code[: max(1, 120 - len(str(suffix)) - 1)]
            code = f"{trimmed}-{suffix}"
            suffix += 1
        borne.terminal_code = code
        borne.save(update_fields=["terminal_code"])
        used_codes.add(code)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0030_user_forced_password_change"),
    ]

    operations = [
        migrations.AddField(
            model_name="borne",
            name="terminal_code",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(populate_terminal_codes, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="borne",
            index=models.Index(fields=["terminal_code"], name="idx_borne_terminal_code"),
        ),
        migrations.AddConstraint(
            model_name="borne",
            constraint=models.UniqueConstraint(
                condition=~Q(terminal_code=""),
                fields=("terminal_code",),
                name="uniq_borne_terminal_code",
            ),
        ),
    ]
