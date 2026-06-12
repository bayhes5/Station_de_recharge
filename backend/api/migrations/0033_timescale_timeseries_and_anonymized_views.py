from django.db import migrations


TIMESERIES_SQL = """
CREATE TABLE IF NOT EXISTS capteur_data_timeseries (
    id_data uuid NOT NULL,
    id_capteur uuid NOT NULL,
    valeur double precision NOT NULL,
    timestamp timestamp with time zone NOT NULL,
    inserted_at timestamp with time zone NOT NULL DEFAULT now(),
    PRIMARY KEY (id_data, timestamp)
);

CREATE TABLE IF NOT EXISTS session_telemetry_timeseries (
    id_telemetry uuid NOT NULL,
    id_session uuid NOT NULL,
    courant double precision NOT NULL,
    tension double precision NOT NULL,
    energie_kwh double precision NOT NULL,
    timestamp timestamp with time zone NOT NULL,
    inserted_at timestamp with time zone NOT NULL DEFAULT now(),
    PRIMARY KEY (id_telemetry, timestamp)
);

SELECT create_hypertable(
    'capteur_data_timeseries',
    'timestamp',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

SELECT create_hypertable(
    'session_telemetry_timeseries',
    'timestamp',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

CREATE INDEX IF NOT EXISTS idx_capteur_ts_capteur_time
ON capteur_data_timeseries (id_capteur, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_session_ts_session_time
ON session_telemetry_timeseries (id_session, timestamp DESC);

DELETE FROM capteur_data_timeseries ts
WHERE NOT EXISTS (
    SELECT 1
    FROM capteur_data cd
    WHERE cd.id_data = ts.id_data
      AND cd.timestamp = ts.timestamp
);

DELETE FROM session_telemetry_timeseries ts
WHERE NOT EXISTS (
    SELECT 1
    FROM session_telemetry st
    WHERE st.id_telemetry = ts.id_telemetry
      AND st.timestamp = ts.timestamp
);

INSERT INTO capteur_data_timeseries (id_data, id_capteur, valeur, timestamp)
SELECT id_data, id_capteur, valeur, timestamp
FROM capteur_data
ON CONFLICT (id_data, timestamp) DO UPDATE
SET id_capteur = EXCLUDED.id_capteur,
    valeur = EXCLUDED.valeur;

INSERT INTO session_telemetry_timeseries (
    id_telemetry,
    id_session,
    courant,
    tension,
    energie_kwh,
    timestamp
)
SELECT id_telemetry, id_session, courant, tension, energie_kwh, timestamp
FROM session_telemetry
ON CONFLICT (id_telemetry, timestamp) DO UPDATE
SET id_session = EXCLUDED.id_session,
    courant = EXCLUDED.courant,
    tension = EXCLUDED.tension,
    energie_kwh = EXCLUDED.energie_kwh;

CREATE OR REPLACE FUNCTION mirror_capteur_data_timeseries()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO capteur_data_timeseries (id_data, id_capteur, valeur, timestamp)
    VALUES (NEW.id_data, NEW.id_capteur, NEW.valeur, NEW.timestamp)
    ON CONFLICT (id_data, timestamp) DO UPDATE
    SET id_capteur = EXCLUDED.id_capteur,
        valeur = EXCLUDED.valeur;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_capteur_data_timeseries ON capteur_data;
CREATE TRIGGER trg_capteur_data_timeseries
AFTER INSERT OR UPDATE OF id_capteur, valeur, timestamp
ON capteur_data
FOR EACH ROW
EXECUTE FUNCTION mirror_capteur_data_timeseries();

CREATE OR REPLACE FUNCTION mirror_session_telemetry_timeseries()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO session_telemetry_timeseries (
        id_telemetry,
        id_session,
        courant,
        tension,
        energie_kwh,
        timestamp
    )
    VALUES (
        NEW.id_telemetry,
        NEW.id_session,
        NEW.courant,
        NEW.tension,
        NEW.energie_kwh,
        NEW.timestamp
    )
    ON CONFLICT (id_telemetry, timestamp) DO UPDATE
    SET id_session = EXCLUDED.id_session,
        courant = EXCLUDED.courant,
        tension = EXCLUDED.tension,
        energie_kwh = EXCLUDED.energie_kwh;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_session_telemetry_timeseries ON session_telemetry;
CREATE TRIGGER trg_session_telemetry_timeseries
AFTER INSERT OR UPDATE OF id_session, courant, tension, energie_kwh, timestamp
ON session_telemetry
FOR EACH ROW
EXECUTE FUNCTION mirror_session_telemetry_timeseries();

ALTER TABLE capteur_data_timeseries SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'id_capteur'
);

ALTER TABLE session_telemetry_timeseries SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'id_session'
);

SELECT add_compression_policy(
    'capteur_data_timeseries',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

SELECT add_compression_policy(
    'session_telemetry_timeseries',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

SELECT add_retention_policy(
    'capteur_data_timeseries',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

SELECT add_retention_policy(
    'session_telemetry_timeseries',
    INTERVAL '365 days',
    if_not_exists => TRUE
);
"""


ANONYMIZED_VIEWS_SQL = """
CREATE OR REPLACE VIEW utilisateur_anonyme AS
SELECT
    md5(id_user::text) AS user_hash,
    statut,
    is_active,
    date_joined::date AS date_creation
FROM utilisateur;

CREATE OR REPLACE VIEW technicien_anonyme AS
SELECT
    md5(t.id_tech::text) AS technicien_hash,
    (t.id_user IS NOT NULL) AS compte_lie,
    COUNT(ts.id_assignment) FILTER (WHERE ts.is_active) AS stations_actives
FROM technicien t
LEFT JOIN technicien_station ts ON ts.id_technicien = t.id_tech
GROUP BY t.id_tech, t.id_user;

CREATE OR REPLACE VIEW journal_securite_anonyme AS
SELECT
    id_log,
    md5(COALESCE(id_user::text, 'anonymous')) AS user_hash,
    action,
    statut,
    date_action,
    '0.0.0.0'::inet AS ip
FROM journal_securite;

CREATE OR REPLACE VIEW supervision_session_anonyme AS
SELECT
    cs.id_session,
    md5(COALESCE(r.id_user::text, 'anonymous')) AS user_hash,
    cs.start_time,
    cs.end_time,
    cs.charge_state,
    r.reference_code,
    e.numero AS emplacement_numero,
    b.numero AS borne_numero,
    s.nom AS station_nom,
    COALESCE(MAX(st.energie_kwh), 0) AS energie_kwh,
    COUNT(st.id_telemetry) AS points_telemetrie
FROM charging_session cs
JOIN reservation r ON r.id_reservation = cs.id_reservation
JOIN emplacement e ON e.id_emplacement = cs.id_emplacement
JOIN borne b ON b.id_borne = e.id_borne
JOIN station s ON s.id_station = e.id_station
LEFT JOIN session_telemetry st ON st.id_session = cs.id_session
GROUP BY
    cs.id_session,
    r.id_user,
    r.reference_code,
    e.numero,
    b.numero,
    s.nom;
"""


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


def setup_timescale_timeseries_and_anonymized_views(apps, schema_editor):
    """Create production TimescaleDB mirror tables and anonymized SQL views."""
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        if _extension_available(cursor, "timescaledb"):
            schema_editor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
            schema_editor.execute(TIMESERIES_SQL)

    schema_editor.execute(ANONYMIZED_VIEWS_SQL)


def remove_timescale_timeseries_and_anonymized_views(apps, schema_editor):
    """Drop reporting views/triggers while preserving source Django tables."""
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute("DROP VIEW IF EXISTS supervision_session_anonyme;")
    schema_editor.execute("DROP VIEW IF EXISTS journal_securite_anonyme;")
    schema_editor.execute("DROP VIEW IF EXISTS technicien_anonyme;")
    schema_editor.execute("DROP VIEW IF EXISTS utilisateur_anonyme;")
    schema_editor.execute("DROP TRIGGER IF EXISTS trg_session_telemetry_timeseries ON session_telemetry;")
    schema_editor.execute("DROP TRIGGER IF EXISTS trg_capteur_data_timeseries ON capteur_data;")
    schema_editor.execute("DROP FUNCTION IF EXISTS mirror_session_telemetry_timeseries();")
    schema_editor.execute("DROP FUNCTION IF EXISTS mirror_capteur_data_timeseries();")
    schema_editor.execute("DROP TABLE IF EXISTS session_telemetry_timeseries;")
    schema_editor.execute("DROP TABLE IF EXISTS capteur_data_timeseries;")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("api", "0032_alter_technicienstation_role"),
    ]

    operations = [
        migrations.RunPython(
            setup_timescale_timeseries_and_anonymized_views,
            remove_timescale_timeseries_and_anonymized_views,
        ),
    ]
