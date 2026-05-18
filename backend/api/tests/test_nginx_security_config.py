from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
NGINX_STATION_CONF = REPO_ROOT / "nginx" / "conf.d" / "station.conf"
NGINX_PROD_CONF = REPO_ROOT / "nginx" / "nginx.prod.conf"
NGINX_PROD_STATION_CONF = REPO_ROOT / "nginx" / "prod.conf.d" / "station.conf"


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


def test_prod_nginx_enables_rate_limits_compression_and_structured_logs():
    """Ensure the production reverse proxy keeps operational guardrails."""
    if not NGINX_PROD_CONF.exists():
        pytest.skip(f"{NGINX_PROD_CONF} is not available in this isolated backend image.")
    config = NGINX_PROD_CONF.read_text(encoding="utf-8")

    assert "log_format main" in config
    assert "$request_time" in config
    assert "gzip on;" in config
    assert "limit_req_zone $binary_remote_addr zone=api_limit" in config
    assert "limit_req_zone $binary_remote_addr zone=auth_limit" in config


def test_prod_nginx_serves_static_assets_with_cache_and_limits_auth():
    """Ensure production Nginx serves static assets efficiently and rate-limits auth."""
    if not NGINX_PROD_STATION_CONF.exists():
        pytest.skip(f"{NGINX_PROD_STATION_CONF} is not available in this isolated backend image.")
    config = NGINX_PROD_STATION_CONF.read_text(encoding="utf-8")

    assert "client_max_body_size 10m;" in config
    assert "ssl_session_tickets off;" in config
    assert 'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;' in config
    assert "location = /api/login/" in config
    assert "limit_req zone=auth_limit" in config
    assert "location /assets/" in config
    assert 'add_header Cache-Control "public, max-age=31536000, immutable" always;' in config
