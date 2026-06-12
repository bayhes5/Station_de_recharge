#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/station/backups}"
RESTORE_DB="${RESTORE_DB:-station_restore_test}"
BACKUP_FILE="${1:-}"

case "$RESTORE_DB" in
    ""|*[!A-Za-z0-9_]*)
        echo "Invalid RESTORE_DB: $RESTORE_DB" >&2
        exit 1
        ;;
esac

if [ -z "$BACKUP_FILE" ]; then
    BACKUP_FILE="$(ls -1t "$BACKUP_DIR"/station_*.sql.gz 2>/dev/null | sed -n '1p')"
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found. Provide a file or set BACKUP_DIR." >&2
    exit 1
fi

if [ -f "$BACKUP_FILE.sha256" ]; then
    sha256sum -c "$BACKUP_FILE.sha256"
fi

cleanup() {
    docker compose -f "$COMPOSE_FILE" --profile simulation exec -T db \
        sh -lc "dropdb -U \"\$POSTGRES_USER\" --if-exists \"$RESTORE_DB\"" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup

docker compose -f "$COMPOSE_FILE" --profile simulation exec -T db \
    sh -lc "createdb -U \"\$POSTGRES_USER\" \"$RESTORE_DB\""

gzip -dc "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" --profile simulation exec -T db \
    sh -lc "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" \"$RESTORE_DB\" >/tmp/${RESTORE_DB}.log"

MIGRATION_COUNT="$(docker compose -f "$COMPOSE_FILE" --profile simulation exec -T db \
    sh -lc "psql -U \"\$POSTGRES_USER\" -d \"$RESTORE_DB\" -tAc 'select count(*) from django_migrations;'")"

echo "Restore test database: $RESTORE_DB"
echo "Restored backup: $BACKUP_FILE"
echo "Django migrations restored: $MIGRATION_COUNT"

cleanup
trap - EXIT
echo "Restore test completed."
