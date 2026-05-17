from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
NGINX_STATION_CONF = REPO_ROOT / "nginx" / "conf.d" / "station.conf"


def _read_station_conf() -> str:
    """Read the reverse-proxy server configuration."""
    if not NGINX_STATION_CONF.exists():
        pytest.skip(f"{NGINX_STATION_CONF} is not available in this isolated backend image.")
    return NGINX_STATION_CONF.read_text(encoding="utf-8")


def test_nginx_security_headers_are_versioned():
    """Ensure the reverse proxy keeps baseline browser security headers."""
    config = _read_station_conf()

    assert 'add_header X-Frame-Options "SAMEORIGIN" always;' in config
    assert 'add_header X-Content-Type-Options "nosniff" always;' in config
    assert 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;' in config
    assert "add_header Content-Security-Policy" in config

    csp_line = next(line.strip() for line in config.splitlines() if "Content-Security-Policy" in line)
    assert "default-src 'self'" in csp_line
    assert "object-src 'none'" in csp_line
    assert "frame-ancestors 'self'" in csp_line
    assert "connect-src 'self' ws: wss:" in csp_line
    assert "https://*.tile.openstreetmap.org" in csp_line


def test_nginx_grafana_location_does_not_inherit_frontend_csp():
    """Keep Grafana isolated from the stricter frontend CSP."""
    config = _read_station_conf()
    grafana_block = config.split("location /grafana/ {", 1)[1].split("location /kiosk/", 1)[0]

    assert "Content-Security-Policy" not in grafana_block
    assert 'add_header X-Frame-Options "SAMEORIGIN" always;' in grafana_block
    assert 'add_header X-Content-Type-Options "nosniff" always;' in grafana_block
