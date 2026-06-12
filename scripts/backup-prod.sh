#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/station/backups}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DOCKER_VOLUMES="${BACKUP_DOCKER_VOLUMES:-false}"
BACKUP_CONFIG="${BACKUP_CONFIG:-true}"
BACKUP_INCLUDE_SECRETS="${BACKUP_INCLUDE_SECRETS:-false}"

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

backup_container_path() {
    container_name="$1"
    source_path="$2"
    output_name="$3"

    if ! docker inspect "$container_name" >/dev/null 2>&1; then
        echo "Skipping $container_name: container not found" >&2
        return
    fi

    output_file="$BACKUP_DIR/${output_name}_${TIMESTAMP}.tar.gz"
    docker exec "$container_name" tar -czf - -C "$source_path" . > "$output_file"
    chmod 600 "$output_file"
    sha256sum "$output_file" > "$output_file.sha256"
    chmod 600 "$output_file.sha256"
    echo "Archive written: $output_file"
}

if [ "$BACKUP_DOCKER_VOLUMES" = "true" ]; then
    backup_container_path station_grafana_supervision /var/lib/grafana grafana
fi

if [ "$BACKUP_CONFIG" = "true" ]; then
    CONFIG_ARCHIVE="$BACKUP_DIR/station_config_${TIMESTAMP}.tar.gz"
    CONFIG_EXCLUDES="
        --exclude=.git
        --exclude=.env
        --exclude=backups
        --exclude=nginx/certs/*.key
        --exclude=mosquitto/config/passwords
        --exclude=mosquitto/certs/*.key
    "

    if [ "$BACKUP_INCLUDE_SECRETS" = "true" ]; then
        CONFIG_EXCLUDES="
            --exclude=.git
            --exclude=backups
        "
    fi

    # shellcheck disable=SC2086
    tar -czf "$CONFIG_ARCHIVE" $CONFIG_EXCLUDES \
        docker-compose.prod.yml \
        nginx \
        postgresql \
        grafana/provisioning \
        grafana/dashboards \
        mosquitto/config \
        scripts \
        .env.example
    chmod 600 "$CONFIG_ARCHIVE"
    sha256sum "$CONFIG_ARCHIVE" > "$CONFIG_ARCHIVE.sha256"
    chmod 600 "$CONFIG_ARCHIVE.sha256"
    echo "Config archive written: $CONFIG_ARCHIVE"
fi
