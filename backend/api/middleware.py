import ipaddress

from django.conf import settings
from django.core.exceptions import DisallowedHost


class DevelopmentPrivateNetworkHostMiddleware:
    """Limit DEBUG host auto-trust to local and private network addresses."""

    INTERNAL_HOSTS = {
        "backend",
        "celery",
        "db",
        "django_app",
        "frontend",
        "grafana",
        "host.docker.internal",
        "localhost",
        "mailpit",
        "mqtt",
        "raspberry",
        "redis",
        "reverse-proxy",
        "testserver",
    }

    def __init__(self, get_response):
        """Store the next middleware or view callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Reject unexpected hosts when DEBUG temporarily trusts private networks."""
        if (
            settings.DEBUG
            and getattr(settings, "DEV_AUTO_TRUST_PRIVATE_NETWORK", False)
            and "*" in settings.ALLOWED_HOSTS
        ):
            host = self._extract_host(request.META.get("HTTP_HOST") or request.META.get("SERVER_NAME", ""))
            if not self._is_allowed_development_host(host):
                raise DisallowedHost(f"Invalid development host: {host}")
        return self.get_response(request)

    @classmethod
    def _extract_host(cls, raw_host):
        """Return the hostname without brackets or port information."""
        host = str(raw_host or "").strip().lower()
        if host.startswith("["):
            end = host.find("]")
            return host[1:end] if end != -1 else host
        return host.rsplit(":", 1)[0] if ":" in host else host

    @classmethod
    def _is_allowed_development_host(cls, host):
        """Return whether a host is acceptable for local DEBUG development."""
        if not host:
            return False
        if host in cls.INTERNAL_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
            return True
        if "." not in host and ":" not in host:
            return True
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return address.is_loopback or address.is_private or address.is_link_local
