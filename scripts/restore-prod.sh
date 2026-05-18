#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: scripts/restore-prod.sh <backup.sql|backup.sql.gz>" >&2
    exit 1
fi

if [ "${RESTORE_CONFIRM:-}" != "YES" ]; then
    echo "Refusing to restore without RESTORE_CONFIRM=YES." >&2
    echo "Example: RESTORE_CONFIRM=YES scripts/restore-prod.sh $BACKUP_FILE" >&2
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE" >&2
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

docker compose -f "$COMPOSE_FILE" stop backend celery celery-beat mqtt-bridge raspberry reverse-proxy

case "$BACKUP_FILE" in
    *.gz)
        gzip -dc "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T db psql \
            -v ON_ERROR_STOP=1 \
            -U "$DB_USER_VALUE" \
            "$DB_NAME_VALUE"
        ;;
    *)
        docker compose -f "$COMPOSE_FILE" exec -T db psql \
            -v ON_ERROR_STOP=1 \
            -U "$DB_USER_VALUE" \
            "$DB_NAME_VALUE" \
            < "$BACKUP_FILE"
        ;;
esac

docker compose -f "$COMPOSE_FILE" up -d backend celery celery-beat mqtt-bridge raspberry reverse-proxy

echo "Restore completed from: $BACKUP_FILE"
