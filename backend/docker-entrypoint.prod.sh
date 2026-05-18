#!/bin/sh
set -eu

python - <<'PY'
import os
import sys
import time

import psycopg2

config = {
    "dbname": os.environ.get("DB_NAME") or os.environ.get("POSTGRES_DB", "station"),
    "user": os.environ.get("DB_USER") or os.environ.get("POSTGRES_USER", "user"),
    "password": os.environ.get("DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD", "password"),
    "host": os.environ.get("DB_HOST", "db"),
    "port": os.environ.get("DB_PORT", "5432"),
    "connect_timeout": 5,
}

for attempt in range(1, 61):
    try:
        connection = psycopg2.connect(**config)
        connection.close()
        print("Database is ready.")
        sys.exit(0)
    except psycopg2.OperationalError as error:
        if attempt == 60:
            print(f"Database is not reachable after {attempt} attempts: {error}", file=sys.stderr)
            sys.exit(1)
        print(f"Waiting for database ({attempt}/60)...")
        time.sleep(2)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py bootstrap_superuser

if [ "${BOOTSTRAP_DEMO_DATA:-False}" = "True" ] || [ "${BOOTSTRAP_DEMO_DATA:-False}" = "true" ]; then
    python manage.py bootstrap_demo_data
fi

exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
