from django.db import migrations


def _extension_available(cursor, extension_name):
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_available_extensions
            WHERE name = %s
        );
        """,
        [extension_name],
    )
    return cursor.fetchone()[0]


def enable_pg_stat_statements_and_timescale_policies(apps, schema_editor):
    """Enable query statistics and Timescale policies when the DB supports them."""
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        if _extension_available(cursor, "pg_stat_statements"):
            schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")

        if not _extension_available(cursor, "timescaledb"):
            return

        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public'
                  AND hypertable_name = 'capteur_data'
            );
            """
        )
        capteur_data_is_hypertable = cursor.fetchone()[0]

    if not capteur_data_is_hypertable:
        return

    # These policies are intentionally conditional. The current schema keeps
    # capteur_data as a classic PostgreSQL table; if a future migration converts
    # it to a hypertable, this migration becomes immediately useful.
    schema_editor.execute(
        """
        ALTER TABLE capteur_data SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'id_capteur'
        );
        """
    )
    schema_editor.execute(
        """
        SELECT add_compression_policy('capteur_data', INTERVAL '7 days', if_not_exists => TRUE);
        """
    )
    schema_editor.execute(
        """
        SELECT add_retention_policy('capteur_data', INTERVAL '90 days', if_not_exists => TRUE);
        """
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0025_device_firmware_policy"),
    ]

    operations = [
        migrations.RunPython(
            enable_pg_stat_statements_and_timescale_policies,
            migrations.RunPython.noop,
        ),
    ]
