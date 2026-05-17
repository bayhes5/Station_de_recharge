import hashlib
from datetime import timedelta

from django.utils import timezone

from api.models import Authentification, TypeAuth


class RfidCredentialConflict(ValueError):
    """Raised when an RFID badge is already linked to another account."""


def hash_secret(secret):
    """Hash an access secret before persisting it."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def get_type_auth(libelle):
    """Return the normalized authentication type record for a mode label."""
    normalized = (libelle or "").strip().lower()
    mapping = {
        "rfid": "RFID",
        "qr": "QR",
        "code": "CODE",
    }
    label = mapping.get(normalized, normalized.upper())
    type_auth, _created = TypeAuth.objects.get_or_create(
        libelle=label,
        defaults={"factor_level": 1 if label == "RFID" else 2},
    )
    return type_auth


def ensure_rfid_auth(user, auth_value, validity_days=3650):
    """Create or refresh the saved RFID credential for a user."""
    if not auth_value:
        raise ValueError("auth_value est obligatoire pour RFID.")

    normalized_value = auth_value.strip()
    if not normalized_value:
        raise ValueError("auth_value est obligatoire pour RFID.")

    type_auth = get_type_auth("RFID")
    secret_hash = hash_secret(normalized_value)
    existing = (
        Authentification.objects.select_related("utilisateur")
        .filter(type_auth=type_auth, hash_valeur=secret_hash, is_active=True)
        .first()
    )
    if existing is not None and existing.utilisateur_id != user.id_user:
        raise RfidCredentialConflict("Ce badge RFID est deja associe a un autre compte.")

    auth_method = (
        Authentification.objects.filter(
            utilisateur=user,
            type_auth=type_auth,
            hash_valeur=secret_hash,
        )
        .order_by("-is_active", "-expiration", "-created_at", "-id_auth")
        .first()
    )
    expiration = timezone.now() + timedelta(days=validity_days)
    if auth_method is None:
        return Authentification.objects.create(
            utilisateur=user,
            type_auth=type_auth,
            hash_valeur=secret_hash,
            display_value=normalized_value,
            expiration=expiration,
        )

    auth_method.display_value = normalized_value
    auth_method.expiration = expiration
    auth_method.is_active = True
    auth_method.save(update_fields=["display_value", "expiration", "is_active"])
    return auth_method


def get_saved_rfid_auth(user):
    """Return the latest active saved RFID credential for a user."""
    type_auth = get_type_auth("RFID")
    return (
        Authentification.objects.filter(
            utilisateur=user,
            type_auth=type_auth,
            is_active=True,
        )
        .exclude(display_value="")
        .order_by("-expiration", "-created_at", "-id_auth")
        .first()
    )
