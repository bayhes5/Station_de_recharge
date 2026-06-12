from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from api.models import (
    Alerte,
    AlertStatus,
    Authentification,
    CapteurData,
    DeviceCommandLog,
    JournalSecurite,
    SessionTelemetry,
    UserStatus,
)


@dataclass(frozen=True)
class TelemetryRetentionResult:
    """Summarize one telemetry retention run."""

    enabled: bool
    retention_days: int
    cutoff: object | None
    deleted: int


@dataclass(frozen=True)
class PrivacyRetentionResult:
    """Summarize one full privacy-retention run."""

    enabled: bool
    cutoffs: dict[str, object | None]
    deleted: dict[str, int]
    anonymized_users: int


RESOLVED_ALERT_STATUSES = {
    AlertStatus.RESOLVED,
    AlertStatus.CLOSED,
    AlertStatus.FERMEE,
    "resolved",
    "closed",
}
ANONYMIZED_EMAIL_DOMAIN = "anonymized.invalid"


def is_anonymized_user_account(user) -> bool:
    """Return whether the account has already been anonymized."""
    email = getattr(user, "email", "") or ""
    return email.lower().endswith(f"@{ANONYMIZED_EMAIL_DOMAIN}")


def _retention_days(setting_name: str, default: int) -> int:
    """Read one retention duration from Django settings."""
    return int(getattr(settings, setting_name, default))


def _delete_older_than(queryset, field_name: str, cutoff):
    """Delete rows older than cutoff and return the deleted row count."""
    deleted, _details = queryset.filter(**{f"{field_name}__lt": cutoff}).delete()
    return deleted


def prune_old_telemetry(now=None) -> TelemetryRetentionResult:
    """Delete telemetry samples older than the configured retention window."""
    retention_days = int(getattr(settings, "TELEMETRY_RETENTION_DAYS", 90))
    if retention_days <= 0:
        return TelemetryRetentionResult(
            enabled=False,
            retention_days=retention_days,
            cutoff=None,
            deleted=0,
        )

    current_time = now or timezone.now()
    cutoff = current_time - timedelta(days=retention_days)
    deleted, _ = CapteurData.objects.filter(timestamp__lt=cutoff).delete()
    return TelemetryRetentionResult(
        enabled=True,
        retention_days=retention_days,
        cutoff=cutoff,
        deleted=deleted,
    )


@transaction.atomic
def anonymize_user_account(
    user,
    *,
    reason: str = "account_anonymization",
) -> dict[str, int | str]:
    """Anonymize one user while preserving technical history for operations."""
    if user.is_superuser:
        raise ValueError("Un superutilisateur ne peut pas être anonymisé depuis ce service.")

    suffix = str(user.id_user).replace("-", "")
    anonymous_pseudo = f"user-{suffix[:24]}"
    anonymous_email = f"user-{suffix}@{ANONYMIZED_EMAIL_DOMAIN}"
    now = timezone.now()

    profile_count = 0
    if hasattr(user, "profil"):
        user.profil.nom = ""
        user.profil.telephone = ""
        user.profil.telephone_verifie = False
        user.profil.save(update_fields=["nom", "telephone", "telephone_verifie"])
        profile_count = 1

    auth_count = 0
    for auth_method in user.authentifications.all():
        auth_method.is_active = False
        auth_method.display_value = ""
        auth_method.metadata = {"anonymized": True, "reason": reason}
        auth_method.expiration = now
        auth_method.hash_valeur = f"anonymized:{auth_method.id_auth}"
        auth_method.save(
            update_fields=[
                "is_active",
                "display_value",
                "metadata",
                "expiration",
                "hash_valeur",
            ]
        )
        auth_count += 1

    security_log_count = user.journaux_securite.update(ip="0.0.0.0")

    technician_count = 0
    if hasattr(user, "technicien_profile"):
        technician = user.technicien_profile
        technician.utilisateur = None
        technician.nom = "Technicien anonymisé"
        technician.email = f"technicien-{suffix}@{ANONYMIZED_EMAIL_DOMAIN}"
        technician.telephone = ""
        technician.save(update_fields=["utilisateur", "nom", "email", "telephone"])
        technician_count = 1

    user.set_unusable_password()
    user.pseudo = anonymous_pseudo
    user.email = anonymous_email
    user.statut = UserStatus.ARCHIVED
    user.is_active = False
    user.is_staff = False
    user.failed_attempts = 0
    user.must_change_password = False
    user.password_reset_at = None
    user.last_login = None
    user.save(
        update_fields=[
            "password",
            "pseudo",
            "email",
            "statut",
            "is_active",
            "is_staff",
            "failed_attempts",
            "must_change_password",
            "password_reset_at",
            "last_login",
        ]
    )

    return {
        "user_id": str(user.id_user),
        "profile_anonymized": profile_count,
        "auth_methods_disabled": auth_count,
        "security_logs_anonymized": security_log_count,
        "technician_profiles_anonymized": technician_count,
    }


def apply_privacy_retention(now=None) -> PrivacyRetentionResult:
    """Apply the production privacy retention policy for personal and technical data."""
    if not bool(getattr(settings, "PRIVACY_RETENTION_ENABLED", True)):
        return PrivacyRetentionResult(
            enabled=False,
            cutoffs={},
            deleted={},
            anonymized_users=0,
        )

    current_time = now or timezone.now()
    cutoffs: dict[str, object | None] = {}
    deleted: dict[str, int] = {}

    telemetry_result = prune_old_telemetry(now=current_time)
    cutoffs["capteur_data"] = telemetry_result.cutoff
    deleted["capteur_data"] = telemetry_result.deleted

    retention_specs = [
        (
            "session_telemetry",
            SessionTelemetry.objects.all(),
            "timestamp",
            "SESSION_TELEMETRY_RETENTION_DAYS",
            365,
        ),
        (
            "device_command_log",
            DeviceCommandLog.objects.all(),
            "timestamp",
            "DEVICE_COMMAND_LOG_RETENTION_DAYS",
            365,
        ),
        (
            "security_log",
            JournalSecurite.objects.all(),
            "date_action",
            "SECURITY_LOG_RETENTION_DAYS",
            365,
        ),
    ]
    for key, queryset, field_name, setting_name, default_days in retention_specs:
        retention_days = _retention_days(setting_name, default_days)
        if retention_days <= 0:
            cutoffs[key] = None
            deleted[key] = 0
            continue
        cutoff = current_time - timedelta(days=retention_days)
        cutoffs[key] = cutoff
        deleted[key] = _delete_older_than(queryset, field_name, cutoff)

    alert_days = _retention_days("ALERT_RETENTION_DAYS", 365)
    if alert_days <= 0:
        cutoffs["resolved_alert"] = None
        deleted["resolved_alert"] = 0
    else:
        alert_cutoff = current_time - timedelta(days=alert_days)
        cutoffs["resolved_alert"] = alert_cutoff
        deleted["resolved_alert"], _details = (
            Alerte.objects.filter(status__in=RESOLVED_ALERT_STATUSES)
            .filter(
                Q(resolved_at__lt=alert_cutoff)
                | Q(resolved_at__isnull=True, last_seen__lt=alert_cutoff)
            )
            .delete()
        )

    auth_days = _retention_days("AUTH_METHOD_RETENTION_DAYS", 90)
    if auth_days <= 0:
        cutoffs["auth_method"] = None
        deleted["auth_method"] = 0
    else:
        auth_cutoff = current_time - timedelta(days=auth_days)
        cutoffs["auth_method"] = auth_cutoff
        deleted["auth_method"], _details = Authentification.objects.filter(
            Q(is_active=False, created_at__lt=auth_cutoff)
            | Q(expiration__isnull=False, expiration__lt=auth_cutoff)
        ).delete()

    anonymization_days = _retention_days("USER_ANONYMIZATION_RETENTION_DAYS", 1095)
    anonymized_users = 0
    if anonymization_days <= 0:
        cutoffs["archived_user"] = None
    else:
        user_cutoff = current_time - timedelta(days=anonymization_days)
        cutoffs["archived_user"] = user_cutoff
        # Import lazily to keep the module compatible with custom user-model tests.
        from django.contrib.auth import get_user_model

        User = get_user_model()
        users_to_anonymize = User.objects.filter(
            is_active=False,
            statut=UserStatus.ARCHIVED,
            date_joined__lt=user_cutoff,
        ).exclude(email__endswith=f"@{ANONYMIZED_EMAIL_DOMAIN}")
        for user in users_to_anonymize:
            anonymize_user_account(user, reason="privacy_retention")
            anonymized_users += 1

    return PrivacyRetentionResult(
        enabled=True,
        cutoffs=cutoffs,
        deleted=deleted,
        anonymized_users=anonymized_users,
    )
