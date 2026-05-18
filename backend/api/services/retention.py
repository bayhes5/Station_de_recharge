from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from api.models import CapteurData


@dataclass(frozen=True)
class TelemetryRetentionResult:
    """Summarize one telemetry retention run."""

    enabled: bool
    retention_days: int
    cutoff: object | None
    deleted: int


def prune_old_telemetry(now=None) -> TelemetryRetentionResult:
    """Delete telemetry samples older than the configured retention window."""
    retention_days = int(getattr(settings, "TELEMETRY_RETENTION_DAYS", 90))
    if retention_days <= 0:
        return TelemetryRetentionResult(enabled=False, retention_days=retention_days, cutoff=None, deleted=0)

    current_time = now or timezone.now()
    cutoff = current_time - timedelta(days=retention_days)
    deleted, _ = CapteurData.objects.filter(timestamp__lt=cutoff).delete()
    return TelemetryRetentionResult(enabled=True, retention_days=retention_days, cutoff=cutoff, deleted=deleted)
