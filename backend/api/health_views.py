"""Health-check endpoints kept separate from business API views."""

import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def _health_result(ok, detail="ok", **extra):
    """Return one normalized health check result."""
    return {
        "ok": bool(ok),
        "detail": detail,
        **extra,
    }


def _check_database_health():
    """Verify that the configured Django database accepts a trivial query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as error:  # noqa: BLE001 - health endpoint must report diagnostics.
        return _health_result(False, str(error), engine=connection.vendor)
    return _health_result(True, engine=connection.vendor)


def _check_cache_health():
    """Verify that the default cache can round-trip a short value."""
    key = "health:ready"
    value = secrets.token_urlsafe(8)
    try:
        cache.set(key, value, timeout=15)
        cached = cache.get(key)
        cache.delete(key)
    except Exception as error:  # noqa: BLE001 - health endpoint must report diagnostics.
        return _health_result(False, str(error))
    if cached != value:
        return _health_result(False, "cache round-trip mismatch")
    return _health_result(True)


def _check_runtime_config_health():
    """Report critical runtime configuration without exposing secrets."""
    terminal_secret_configured = bool(getattr(settings, "TERMINAL_API_SECRET", ""))
    detail = "ok"
    if not terminal_secret_configured:
        detail = "TERMINAL_API_SECRET missing in debug mode" if settings.DEBUG else "TERMINAL_API_SECRET missing"
    return _health_result(
        settings.DEBUG or terminal_secret_configured,
        detail,
        debug=settings.DEBUG,
        terminal_secret_configured=terminal_secret_configured,
    )


def _schema(summary, tags=None):
    """Build a small drf-spectacular decorator for health endpoints."""
    return extend_schema(
        summary=summary,
        responses=OpenApiTypes.OBJECT,
        tags=tags or ["Sante"],
    )


@_schema("Verifier que l'API repond", tags=["Sante"])
@api_view(["GET"])
@permission_classes([AllowAny])
def health_live(_request):
    """Return a lightweight liveness probe for load balancers."""
    return Response(
        {
            "status": "ok",
            "service": "station-backend",
            "timestamp": timezone.now().isoformat(),
        }
    )


@_schema("Verifier que l'API est prete", tags=["Sante"])
@api_view(["GET"])
@permission_classes([AllowAny])
def health_ready(_request):
    """Return readiness checks for critical runtime dependencies."""
    checks = {
        "database": _check_database_health(),
        "cache": _check_cache_health(),
        "config": _check_runtime_config_health(),
    }
    ok = all(check["ok"] for check in checks.values())
    return Response(
        {
            "status": "ok" if ok else "degraded",
            "service": "station-backend",
            "timestamp": timezone.now().isoformat(),
            "checks": checks,
        },
        status=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
