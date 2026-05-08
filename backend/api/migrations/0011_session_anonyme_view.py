# Generated for PostgreSQL reporting views.

from django.db import migrations


SESSION_ANONYME_SQL = """
CREATE OR REPLACE VIEW session_anonyme AS
SELECT
    cs.id_session,
    cs.start_time AS date_debut,
    cs.end_time AS date_fin,
    COALESCE(MAX(st.energie_kwh), 0)::double precision AS consommation_kwh,
    md5(COALESCE(r.id_user::text, cs.id_session::text)) AS user_hash
FROM charging_session cs
JOIN reservation r ON r.id_reservation = cs.id_reservation
LEFT JOIN session_telemetry st ON st.id_session = cs.id_session
GROUP BY cs.id_session, cs.start_time, cs.end_time, r.id_user;
"""


def create_session_anonyme_view(apps, schema_editor):
    """Create the anonymized session reporting view on PostgreSQL."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(SESSION_ANONYME_SQL)


def drop_session_anonyme_view(apps, schema_editor):
    """Drop the anonymized session reporting view on PostgreSQL."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP VIEW IF EXISTS session_anonyme;")


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_telemetry_query_indexes"),
    ]

    operations = [
        migrations.RunPython(create_session_anonyme_view, drop_session_anonyme_view),
    ]
