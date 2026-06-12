#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${KIOSK_APP_DIR:-/home/btsciel/raspberry/app}"
PID_FILE="${KIOSK_PID_FILE:-$APP_DIR/kiosk.pid}"
LOG_FILE="${KIOSK_LOG_FILE:-$APP_DIR/kiosk.log}"

if [ ! -d "$APP_DIR" ]; then
  echo "Kiosk app directory not found: $APP_DIR" >&2
  exit 1
fi

cd "$APP_DIR"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Stopping kiosk process $OLD_PID"
    kill "$OLD_PID" || true
    sleep 1
  fi
fi

if pgrep -f "$APP_DIR/main.py" >/dev/null 2>&1; then
  echo "Stopping remaining kiosk Python processes"
  pkill -f "$APP_DIR/main.py" || true
  sleep 1
fi

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

export BACKEND_API_BASE_URL="${BACKEND_API_BASE_URL:-http://172.20.10.8:8000/api}"
export TERMINAL_API_SECRET="${TERMINAL_API_SECRET:-dev-terminal-secret}"
export TERMINAL_CODE="${TERMINAL_CODE:-station-demo-borne-1}"
export TERMINAL_STATION_ID="${TERMINAL_STATION_ID:-}"
export TERMINAL_BORNE_ID="${TERMINAL_BORNE_ID:-}"

export MQTT_HOST="${MQTT_HOST:-localhost}"
export MQTT_PORT="${MQTT_PORT:-1883}"
export MQTT_BASE_TOPIC="${MQTT_BASE_TOPIC:-station}"
export MQTT_USERNAME="${MQTT_USERNAME:-raspberry_kiosk}"
export MQTT_PASSWORD="${MQTT_PASSWORD:-TEST}"
export MQTT_TLS_ENABLED="${MQTT_TLS_ENABLED:-false}"
export MQTT_TLS_CA_CERT="${MQTT_TLS_CA_CERT:-}"
export MQTT_QOS="${MQTT_QOS:-1}"
export MQTT_ACK_TIMEOUT_SECONDS="${MQTT_ACK_TIMEOUT_SECONDS:-8}"
export MQTT_ACK_REQUIRED="${MQTT_ACK_REQUIRED:-true}"

export RFID_READER_BACKEND="${RFID_READER_BACKEND:-acr122u}"
export RFID_DEBOUNCE_SECONDS="${RFID_DEBOUNCE_SECONDS:-2}"

echo "Starting kiosk:"
echo "  APP_DIR=$APP_DIR"
echo "  BACKEND_API_BASE_URL=$BACKEND_API_BASE_URL"
echo "  MQTT_HOST=$MQTT_HOST:$MQTT_PORT"
echo "  MQTT_USERNAME=$MQTT_USERNAME"
echo "  MQTT_TLS_ENABLED=$MQTT_TLS_ENABLED"
echo "  MQTT_TLS_CA_CERT=${MQTT_TLS_CA_CERT:-<none>}"
echo "  MQTT_PASSWORD=<hidden>"
echo "  TERMINAL_CODE=$TERMINAL_CODE"

nohup python main.py >"$LOG_FILE" 2>&1 &
NEW_PID="$!"
echo "$NEW_PID" > "$PID_FILE"

echo "Kiosk started with PID $NEW_PID"
echo "Logs: $LOG_FILE"
