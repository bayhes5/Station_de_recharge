#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF_SRC="$ROOT_DIR/mosquitto/station.conf"
ACL_SRC="$ROOT_DIR/mosquitto/aclfile"
CONF_DST="/etc/mosquitto/conf.d/station.conf"
ACL_DST="/etc/mosquitto/aclfile"
PASSWD_DST="/etc/mosquitto/passwd"

read_secret() {
  local var_name="$1"
  local label="$2"
  local current="${!var_name:-}"
  if [ -n "$current" ]; then
    printf '%s' "$current"
    return
  fi
  local value=""
  read -r -s -p "$label: " value
  echo >&2
  printf '%s' "$value"
}

require_file() {
  local path="$1"
  if [ ! -f "$path" ]; then
    echo "Missing file: $path" >&2
    exit 1
  fi
}

require_file "$CONF_SRC"
require_file "$ACL_SRC"

BACKEND_PASSWORD="$(read_secret MQTT_BACKEND_PASSWORD 'Mot de passe MQTT backend')"
RASPBERRY_PASSWORD="$(read_secret MQTT_RASPBERRY_PASSWORD 'Mot de passe MQTT Raspberry')"
ESP32_SLOT1_PASSWORD="$(read_secret MQTT_ESP32_SLOT1_PASSWORD 'Mot de passe MQTT ESP32 slot1')"
ESP32_SLOT2_PASSWORD="${MQTT_ESP32_SLOT2_PASSWORD:-}"
ESP32_SLOT3_PASSWORD="${MQTT_ESP32_SLOT3_PASSWORD:-}"

sudo apt update
sudo apt install -y mosquitto mosquitto-clients

sudo install -o root -g root -m 0644 "$CONF_SRC" "$CONF_DST"
sudo install -o root -g root -m 0644 "$ACL_SRC" "$ACL_DST"

sudo rm -f "$PASSWD_DST"
sudo mosquitto_passwd -b -c "$PASSWD_DST" station_backend "$BACKEND_PASSWORD"
sudo mosquitto_passwd -b "$PASSWD_DST" raspberry_kiosk "$RASPBERRY_PASSWORD"
sudo mosquitto_passwd -b "$PASSWD_DST" esp32_station_demo_borne_1_slot1 "$ESP32_SLOT1_PASSWORD"

if [ -n "$ESP32_SLOT2_PASSWORD" ]; then
  sudo mosquitto_passwd -b "$PASSWD_DST" esp32_station_demo_borne_1_slot2 "$ESP32_SLOT2_PASSWORD"
fi

if [ -n "$ESP32_SLOT3_PASSWORD" ]; then
  sudo mosquitto_passwd -b "$PASSWD_DST" esp32_station_demo_borne_1_slot3 "$ESP32_SLOT3_PASSWORD"
fi

sudo chown root:mosquitto "$PASSWD_DST"
sudo chmod 0640 "$PASSWD_DST"
sudo chmod 0644 "$ACL_DST" "$CONF_DST"

sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sudo systemctl --no-pager --full status mosquitto

RASPBERRY_IP="$(hostname -I | awk '{print $1}')"

echo
echo "Mosquitto Raspberry prêt."
echo "IP Raspberry probable: ${RASPBERRY_IP:-inconnue}"
echo
echo "Test local:"
echo "  mosquitto_sub -h localhost -u raspberry_kiosk -P '<mot-de-passe>' -t 'station/#' -v"
echo
echo "Backend/bridge doit utiliser:"
echo "  MQTT_HOST=${RASPBERRY_IP:-<ip-raspberry>}"
echo "  MQTT_USERNAME=station_backend"
echo
echo "Raspberry kiosk doit utiliser:"
echo "  MQTT_HOST=localhost"
echo "  MQTT_USERNAME=raspberry_kiosk"
echo
echo "ESP32 slot1 doit utiliser:"
echo "  MQTT_HOST='${RASPBERRY_IP:-<ip-raspberry>}'"
echo "  MQTT_USER='esp32_station_demo_borne_1_slot1'"
