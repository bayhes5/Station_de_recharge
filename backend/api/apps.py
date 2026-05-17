from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configure the Django application that exposes the charging station API."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        """Register application-specific deployment checks."""
        from . import checks  # noqa: F401
