# Enable TimescaleDB when the PostgreSQL server provides the extension.

from django.db import migrations


def enable_timescaledb_extension(apps, schema_editor):
    """Enable TimescaleDB on PostgreSQL deployments that provide it."""
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_available_extensions
                WHERE name = 'timescaledb'
            );
            """
        )
        extension_available = cursor.fetchone()[0]

    if extension_available:
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_alerte_chk_alert_severity_alerte_chk_alert_status_and_more"),
    ]

    operations = [
        migrations.RunPython(enable_timescaledb_extension, migrations.RunPython.noop),
    ]
