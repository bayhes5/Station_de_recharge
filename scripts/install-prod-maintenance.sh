#!/usr/bin/env sh
set -eu

STATION_DIR="${STATION_DIR:-/opt/station}"
BACKUP_DIR="${BACKUP_DIR:-/opt/station/backups}"
BACKUP_LOG="${BACKUP_LOG:-/var/log/station-backup.log}"
STATION_OWNER="${STATION_OWNER:-${SUDO_USER:-station}}"
STATION_GROUP="${STATION_GROUP:-$STATION_OWNER}"
BACKUP_HOUR="${BACKUP_HOUR:-2}"
BACKUP_MINUTE="${BACKUP_MINUTE:-15}"
SKIP_APT="${SKIP_APT:-false}"
APPLY_UFW="${APPLY_UFW:-false}"
APPLY_SSH_HARDENING="${APPLY_SSH_HARDENING:-false}"
DISABLE_SSH_PASSWORD_AUTH="${DISABLE_SSH_PASSWORD_AUTH:-false}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo $0" >&2
    exit 1
fi

if [ ! -d "$STATION_DIR" ]; then
    echo "Station directory not found: $STATION_DIR" >&2
    exit 1
fi

if [ "$SKIP_APT" != "true" ]; then
    apt-get update
    apt-get install -y unattended-upgrades fail2ban logrotate ufw
fi

cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

mkdir -p /etc/fail2ban/jail.d
cat >/etc/fail2ban/jail.d/station-sshd.conf <<'EOF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 30m
EOF
systemctl enable --now fail2ban

mkdir -p "$BACKUP_DIR"
chown "$STATION_OWNER":"$STATION_GROUP" "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
touch "$BACKUP_LOG"
chown "$STATION_OWNER":"$STATION_GROUP" "$BACKUP_LOG"
chmod 640 "$BACKUP_LOG"

cat >/etc/cron.d/station-backup <<EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

${BACKUP_MINUTE} ${BACKUP_HOUR} * * * ${STATION_OWNER} cd ${STATION_DIR} && BACKUP_DOCKER_VOLUMES=true BACKUP_CONFIG=true BACKUP_DIR=${BACKUP_DIR} scripts/backup-prod.sh >> ${BACKUP_LOG} 2>&1
EOF
chmod 644 /etc/cron.d/station-backup

cat >/etc/logrotate.d/station-backup <<'EOF'
__BACKUP_LOG__ {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    create 0640 __STATION_OWNER__ __STATION_GROUP__
}
EOF
sed -i "s|__BACKUP_LOG__|$BACKUP_LOG|g; s|__STATION_OWNER__|$STATION_OWNER|g; s|__STATION_GROUP__|$STATION_GROUP|g" /etc/logrotate.d/station-backup

if [ "$APPLY_SSH_HARDENING" = "true" ]; then
    mkdir -p /etc/ssh/sshd_config.d
    {
        echo "PermitRootLogin no"
        echo "PubkeyAuthentication yes"
        echo "MaxAuthTries 3"
        if [ "$DISABLE_SSH_PASSWORD_AUTH" = "true" ]; then
            echo "PasswordAuthentication no"
        fi
    } >/etc/ssh/sshd_config.d/99-station-hardening.conf
    sshd -t
    systemctl restart ssh
fi

if [ "$APPLY_UFW" = "true" ]; then
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
fi

echo "Production maintenance installed."
echo "Backup cron: ${BACKUP_MINUTE} ${BACKUP_HOUR} * * *"
echo "Backup dir: $BACKUP_DIR"
