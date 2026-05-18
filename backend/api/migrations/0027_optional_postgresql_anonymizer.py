from django.db import migrations


ANONYMIZER_LABELS = [
    (
        "utilisateur",
        "pseudo",
        "MASKED WITH VALUE 'utilisateur-anonyme'",
    ),
    (
        "utilisateur",
        "email",
        "MASKED WITH VALUE 'utilisateur@example.invalid'",
    ),
    (
        "profil_utilisateur",
        "nom",
        "MASKED WITH VALUE 'Utilisateur anonymise'",
    ),
    (
        "profil_utilisateur",
        "telephone",
        "MASKED WITH VALUE '0000000000'",
    ),
    (
        "journal_securite",
        "ip",
        "MASKED WITH VALUE '0.0.0.0'",
    ),
    (
        "technicien",
        "nom",
        "MASKED WITH VALUE 'Technicien anonymise'",
    ),
    (
        "technicien",
        "email",
        "MASKED WITH VALUE 'technicien@example.invalid'",
    ),
    (
        "technicien",
        "telephone",
        "MASKED WITH VALUE '0000000000'",
    ),
]


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


def _function_available(cursor, signature):
    cursor.execute("SELECT to_regprocedure(%s) IS NOT NULL;", [signature])
    return cursor.fetchone()[0]


def enable_optional_postgresql_anonymizer(apps, schema_editor):
    """Enable PostgreSQL Anonymizer masks when the DB image provides anon."""
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        if not _extension_available(cursor, "anon"):
            return

        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS anon CASCADE;")

        if _function_available(cursor, "anon.init()"):
            schema_editor.execute("SELECT anon.init();")

    for table_name, column_name, masking_rule in ANONYMIZER_LABELS:
        escaped_rule = masking_rule.replace("'", "''")
        schema_editor.execute(
            f"SECURITY LABEL FOR anon ON COLUMN {table_name}.{column_name} IS '{escaped_rule}';"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0026_pg_stat_statements_and_timescale_policies"),
    ]

    operations = [
        migrations.RunPython(
            enable_optional_postgresql_anonymizer,
            migrations.RunPython.noop,
        ),
    ]
