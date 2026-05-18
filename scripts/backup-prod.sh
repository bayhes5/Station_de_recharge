#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/station/backups}"
ENV_FILE="${ENV_FILE:-.env}"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Compose file not found: $COMPOSE_FILE" >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Environment file not found: $ENV_FILE" >&2
    exit 1
fi

env_value() {
    key="$1"
    awk -v key="$key" 'index($0, key "=") == 1 { value = substr($0, length(key) + 2) } END { print value }' "$ENV_FILE"
}

DB_USER_VALUE="$(env_value POSTGRES_USER)"
if [ -z "$DB_USER_VALUE" ]; then
    DB_USER_VALUE="$(env_value DB_USER)"
fi
if [ -z "$DB_USER_VALUE" ]; then
    DB_USER_VALUE="user"
fi

DB_NAME_VALUE="$(env_value POSTGRES_DB)"
if [ -z "$DB_NAME_VALUE" ]; then
    DB_NAME_VALUE="$(env_value DB_NAME)"
fi
if [ -z "$DB_NAME_VALUE" ]; then
    DB_NAME_VALUE="station"
fi
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_SQL="$BACKUP_DIR/station_${TIMESTAMP}.sql"
OUTPUT_GZ="$OUTPUT_SQL.gz"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

docker compose -f "$COMPOSE_FILE" exec -T db pg_dump \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -U "$DB_USER_VALUE" \
    "$DB_NAME_VALUE" \
    > "$OUTPUT_SQL"

gzip -f "$OUTPUT_SQL"
chmod 600 "$OUTPUT_GZ"

sha256sum "$OUTPUT_GZ" > "$OUTPUT_GZ.sha256"
chmod 600 "$OUTPUT_GZ.sha256"

echo "Backup written: $OUTPUT_GZ"
echo "Checksum written: $OUTPUT_GZ.sha256"
