from __future__ import annotations

from datetime import timedelta


RESERVATION_DURATION_MINUTES = (30, 60, 120, 240)
DEFAULT_RESERVATION_DURATION_MINUTES = 60
RESERVATION_STEP_MINUTES = 30


def reservation_duration_minutes(date_debut, date_fin) -> int | None:
    """Return the reservation duration in minutes when it is exact."""
    duration = date_fin - date_debut
    total_seconds = duration.total_seconds()
    if total_seconds <= 0 or total_seconds % 60 != 0:
        return None
    return int(total_seconds // 60)


def reservation_duration_is_allowed(date_debut, date_fin) -> bool:
    """Return whether a reservation duration is one of the supported choices."""
    return reservation_duration_minutes(date_debut, date_fin) in RESERVATION_DURATION_MINUTES


def default_reservation_end(date_debut):
    """Return the default reservation end for a new booking."""
    return date_debut + timedelta(minutes=DEFAULT_RESERVATION_DURATION_MINUTES)


def reservation_duration_error_message() -> str:
    """Return the user-facing duration validation message."""
    labels = ["30 minutes", "1 heure", "2 heures", "4 heures"]
    return "La durée de recharge doit être l'une des valeurs suivantes: " + ", ".join(labels) + "."
