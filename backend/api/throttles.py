from rest_framework.throttling import SimpleRateThrottle


class ClientScopedRateThrottle(SimpleRateThrottle):
    """Throttle a sensitive endpoint by authenticated user or client IP."""

    scope = None

    def get_cache_key(self, request, view):
        """Build a stable cache key for the configured throttle scope."""
        if not self.scope:
            return None

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            ident = f"user:{user.pk}"
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class LoginRateThrottle(ClientScopedRateThrottle):
    """Limit credential guessing on login."""

    scope = "login"


class RegistrationRateThrottle(ClientScopedRateThrottle):
    """Limit abusive account registration and availability probing."""

    scope = "register"


class TokenRefreshRateThrottle(ClientScopedRateThrottle):
    """Limit refresh token replay attempts."""

    scope = "token_refresh"


class AuthFactorRateThrottle(ClientScopedRateThrottle):
    """Limit RFID and access-factor setup endpoints."""

    scope = "auth_factor"


class SmsRateThrottle(ClientScopedRateThrottle):
    """Limit SMS access-code resend attempts."""

    scope = "sms"


class TerminalRateThrottle(ClientScopedRateThrottle):
    """Limit kiosk-facing terminal calls by client or terminal IP."""

    scope = "terminal"


class MobileSessionRateThrottle(ClientScopedRateThrottle):
    """Limit mobile pairing session reads and authorizations."""

    scope = "mobile_session"
