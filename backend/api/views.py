import base64
import hashlib
import hmac
import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from io import BytesIO
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import (
    validate_password as validate_django_password,
)
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Authentification,
    Borne,
    Consentement,
    Device,
    DeviceStatus,
    Emplacement,
    JournalSecurite,
    Maintenance,
    ProfilUtilisateur,
    Reservation,
    Station,
    Technicien,
    TechnicienStation,
    UserStatus,
)
from .models import (
    Session as ChargingSession,
)
from .permissions import IsStaffUser
from .reservation_rules import (
    RESERVATION_DURATION_MINUTES,
    RESERVATION_STEP_MINUTES,
    reservation_duration_error_message,
    reservation_duration_is_allowed,
    reservation_duration_minutes,
)
from .serializers import (
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    BorneSerializer,
    ConsentPreferenceSerializer,
    DeviceAdminSerializer,
    EmplacementSerializer,
    MaintenanceAdminSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    StationSerializer,
    TechnicianMaintenanceSerializer,
    TechnicianSerializer,
    TechnicianStationAssignmentSerializer,
)
from .services.alert_workflow import (
    AlertWorkflowError,
    acknowledge_alert,
    alert_queryset,
    alert_station_id,
    resolve_alert,
)
from .services.auth_methods import (
    RfidCredentialConflict,
)
from .services.auth_methods import (
    ensure_rfid_auth as _ensure_rfid_auth,
)
from .services.auth_methods import (
    get_saved_rfid_auth as _get_saved_rfid_auth,
)
from .services.auth_methods import (
    get_type_auth as _get_type_auth,
)
from .services.auth_methods import (
    hash_secret as _hash_secret,
)
from .services.charge_session_state import (
    ChargeSessionStateError,
    mark_access_validated,
    mark_stop_requested,
    mark_stopped,
)
from .services.email_notifications import send_reservation_qr_email
from .services.firmware import schedule_ota_update, update_firmware_compliance_status
from .services.sms import SmsDeliveryError, mask_phone_number, send_sms
from .services.sms_access_policy import (
    configured_sms_access_code_alphabet,
    configured_sms_access_code_length,
    configured_sms_access_code_max_attempts,
    sms_access_code_policy_payload,
)
from .services.supervision import (
    build_admin_supervision_payload,
    serialize_alert_supervision,
)
from .throttles import (
    AuthFactorRateThrottle,
    LoginRateThrottle,
    MobileSessionRateThrottle,
    RegistrationRateThrottle,
    SmsRateThrottle,
    TerminalRateThrottle,
    TokenRefreshRateThrottle,
)

logger = logging.getLogger(__name__)
User = get_user_model()
RESERVATION_START_GRACE_MINUTES = getattr(settings, "RESERVATION_START_GRACE_MINUTES", 5)
RESERVATION_END_GRACE_MINUTES = getattr(settings, "RESERVATION_END_GRACE_MINUTES", 10)
DEFAULT_SESSION_MAX_MINUTES = getattr(settings, "CHARGING_SESSION_MAX_MINUTES", 240)
ADMIN_TEMPORARY_PASSWORD_LENGTH = 16
ADMIN_TEMPORARY_PASSWORD_SPECIALS = "!@#$%&*-_?"
LIST_PAGINATION_QUERY_PARAMS = {"page", "page_size"}
STATIONS_CATALOG_CACHE_KEY = "api:stations_catalog:v1"
KEYPAD_CODE_ALPHABET = configured_sms_access_code_alphabet()
RESERVATION_CODE_LENGTH = 8
TEMPORARY_CODE_LENGTH = configured_sms_access_code_length()
SMS_ACCESS_CODE_MAX_ATTEMPTS = configured_sms_access_code_max_attempts()
ALERT_WORKFLOW_ERROR_DETAIL = "Transition d'alerte refusée."
CHARGE_SESSION_STATE_ERROR_DETAIL = "Transition de session de charge refusée."
RFID_LINK_CODE_LENGTH = 4
RFID_LINK_CODE_TTL_SECONDS = 10 * 60
MOBILE_SESSION_TTL_SECONDS = getattr(settings, "MOBILE_SESSION_TTL_SECONDS", 10 * 60)
MOBILE_SESSION_TOKEN_BYTES = 18
OFFLINE_CACHE_HORIZON_HOURS = getattr(settings, "TERMINAL_OFFLINE_CACHE_HOURS", 24)
PRIVILEGED_USER_FIELDS = {"is_staff", "is_superuser"}
CONSENT_DEFINITIONS = {
    "cgu": {
        "label": "Conditions générales d'utilisation",
        "required": True,
        "modifiable": False,
    },
    "politique_confidentialite": {
        "label": "Politique de confidentialité",
        "required": True,
        "modifiable": False,
    },
    "notifications": {
        "label": "Notifications optionnelles",
        "required": False,
        "modifiable": True,
    },
}

def _refresh_cookie_kwargs():
    """Return the shared security attributes for the refresh-token cookie."""
    return {
        "httponly": True,
        "secure": settings.JWT_REFRESH_COOKIE_SECURE,
        "samesite": settings.JWT_REFRESH_COOKIE_SAMESITE,
        "path": settings.JWT_REFRESH_COOKIE_PATH,
    }


def _set_refresh_cookie(response, refresh_token):
    """Store the refresh token in an HttpOnly cookie instead of JavaScript storage."""
    max_age = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        str(refresh_token),
        max_age=max_age,
        **_refresh_cookie_kwargs(),
    )
    return response


def _clear_refresh_cookie(response):
    """Remove the refresh-token cookie on logout or invalid session state."""
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )
    return response


class OptionalPageNumberPagination(PageNumberPagination):
    """Paginate function-based list endpoints when the client requests it."""

    page_size = settings.API_DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = settings.API_MAX_PAGE_SIZE


def _serialize_collection(items, serializer_class=None, serializer_func=None):
    """Serialize a queryset or list with either a DRF serializer or function."""
    if serializer_class is not None:
        return serializer_class(items, many=True).data
    return [serializer_func(item) for item in items]


def _list_response(request, queryset, serializer_class=None, serializer_func=None):
    """Return a list response, with opt-in page/page_size pagination."""
    if not LIST_PAGINATION_QUERY_PARAMS.intersection(request.query_params):
        return Response(
            {
                "results": _serialize_collection(
                    queryset,
                    serializer_class=serializer_class,
                    serializer_func=serializer_func,
                )
            }
        )

    paginator = OptionalPageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        _serialize_collection(
            page,
            serializer_class=serializer_class,
            serializer_func=serializer_func,
        )
    )


def _clear_station_catalog_cache():
    """Invalidate cached station catalog data after station or bay changes."""
    cache.delete(STATIONS_CATALOG_CACHE_KEY)


def _client_ip(request):
    """Return the best effort client IP for audit entries."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def _log_security_event(request, target_user, action, statut="success"):
    """Persist a compact security audit event."""
    JournalSecurite.objects.create(
        utilisateur=target_user,
        action=action,
        ip=_client_ip(request),
        statut=statut,
    )


def _terminal_secret_response(request):
    """Return an error response when a protected terminal call lacks the shared secret."""
    expected_secret = getattr(settings, "TERMINAL_API_SECRET", "").strip()
    if not expected_secret:
        if settings.DEBUG:
            return None
        logger.critical("TERMINAL_API_SECRET is missing; terminal API is unavailable.")
        return Response(
            {"detail": "Configuration terminal indisponible."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    provided_secret = (request.headers.get("X-Terminal-Secret") or "").strip()
    authorization = (request.headers.get("Authorization") or "").strip()
    if not provided_secret and authorization.lower().startswith("bearer "):
        provided_secret = authorization.split(" ", 1)[1].strip()

    if hmac.compare_digest(provided_secret, expected_secret):
        return None

    return Response({"detail": "Terminal non autorisé."}, status=status.HTTP_401_UNAUTHORIZED)


def _schema(
    summary,
    request=None,
    responses=OpenApiTypes.OBJECT,
    parameters=None,
    tags=None,
    operation_id=None,
    methods=None,
):
    """Build a reusable drf-spectacular schema decorator for API views."""
    return extend_schema(
        summary=summary,
        request=request,
        responses=responses,
        parameters=parameters,
        tags=tags or ["API"],
        operation_id=operation_id,
        methods=methods,
    )


def _serialize_user(user):
    """Return the account payload shared by authentication and profile views."""
    profile = getattr(user, "profil", None)
    return {
        "id": str(user.id_user),
        "pseudo": user.pseudo,
        "email": user.email,
        "telephone": getattr(profile, "telephone", ""),
        "telephone_verifie": getattr(profile, "telephone_verifie", False),
        "statut": user.statut,
        "nom": getattr(profile, "nom", ""),
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_technician": _user_is_technician(user),
    }


def _get_or_create_profile(user):
    """Return the profile for a user, creating the default record when absent."""
    profile, _created = ProfilUtilisateur.objects.get_or_create(
        utilisateur=user,
        defaults={"nom": user.pseudo, "telephone": ""},
    )
    return profile


def _serialize_consent(consent):
    """Return a compact consent history entry."""
    return {
        "id": str(consent.id_consentement),
        "type": consent.type,
        "label": CONSENT_DEFINITIONS.get(consent.type, {}).get("label", consent.type),
        "statut": consent.statut,
        "date_consentement": consent.date_consentement.isoformat() if consent.date_consentement else None,
    }


def _serialize_user_consents(user):
    """Return the latest consent state per known type plus full history."""
    history = list(user.consentements.all().order_by("-date_consentement"))
    latest_by_type = {}
    for consent in history:
        latest_by_type.setdefault(consent.type, consent)

    current = []
    for consent_type, definition in CONSENT_DEFINITIONS.items():
        latest = latest_by_type.get(consent_type)
        current.append(
            {
                "type": consent_type,
                "label": definition["label"],
                "statut": latest.statut if latest else "non_renseigne",
                "date_consentement": (
                    latest.date_consentement.isoformat()
                    if latest and latest.date_consentement
                    else None
                ),
                "required": definition["required"],
                "modifiable": definition["modifiable"],
            }
        )

    return {
        "current": current,
        "history": [_serialize_consent(consent) for consent in history],
    }


def _as_bool(value):
    """Coerce form-like boolean values from API payloads."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _payload_requests_privileged_role(payload):
    """Return whether an admin payload modifies staff or superuser privileges."""
    return any(field in payload for field in PRIVILEGED_USER_FIELDS)


def _forbid_privileged_role_change_response(request, payload):
    """Block non-superusers from changing administrator-level role flags."""
    if request.user.is_superuser or not _payload_requests_privileged_role(payload):
        return None
    return Response(
        {"detail": "Seul un super-administrateur peut modifier les roles administrateur."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _shuffle_secret(characters):
    """Shuffle password characters with the system random source."""
    shuffled = list(characters)
    for index in range(len(shuffled) - 1, 0, -1):
        swap_index = secrets.randbelow(index + 1)
        shuffled[index], shuffled[swap_index] = shuffled[swap_index], shuffled[index]
    return "".join(shuffled)


def _generate_temporary_password(user):
    """Generate a password that satisfies Django and project complexity rules."""
    alphabet = string.ascii_letters + string.digits + ADMIN_TEMPORARY_PASSWORD_SPECIALS

    for _attempt in range(100):
        required_characters = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice(ADMIN_TEMPORARY_PASSWORD_SPECIALS),
        ]
        remaining_length = ADMIN_TEMPORARY_PASSWORD_LENGTH - len(required_characters)
        password = _shuffle_secret(
            required_characters
            + [secrets.choice(alphabet) for _index in range(remaining_length)]
        )

        try:
            validate_django_password(password, user=user)
        except ValidationError:
            continue

        return password

    raise RuntimeError("Impossible de générer un mot de passe temporaire conforme.")


def _serialize_reservation(reservation):
    """Return a frontend-friendly reservation representation."""
    return {
        "id": str(reservation.id_reservation),
        "id_reservation": str(reservation.id_reservation),
        "reference_code": reservation.reference_code,
        "utilisateur": str(reservation.utilisateur_id) if reservation.utilisateur_id else None,
        "utilisateur_pseudo": reservation.utilisateur.pseudo if reservation.utilisateur else "-",
        "station": reservation.emplacement.station.nom,
        "station_nom": reservation.emplacement.station.nom,
        "borne": reservation.emplacement.borne.nom,
        "borne_nom": reservation.emplacement.borne.nom,
        "borne_numero": reservation.emplacement.borne.numero,
        "mqtt_prefix": reservation.emplacement.borne.mqtt_prefix,
        "emplacement": reservation.emplacement.numero,
        "emplacement_numero": reservation.emplacement.numero,
        "date_debut": reservation.date_debut.isoformat(),
        "date_fin": reservation.date_fin.isoformat(),
        "duration_minutes": reservation_duration_minutes(reservation.date_debut, reservation.date_fin),
        "statut": reservation.statut,
        "auth_mode": reservation.auth_choice,
        "can_cancel": _reservation_can_be_cancelled(reservation),
    }


def _device_slot_id(device, emplacement):
    """Return the logical MQTT slot identifier for a charging bay."""
    if device and (device.slot_id or device.mac_address):
        return device.slot_id or device.mac_address
    return f"slot{emplacement.numero}"


def _serialize_session(session):
    """Return a compact representation of a charging session."""
    device = getattr(session.emplacement, "device", None)
    return {
        "id": str(session.id_session),
        "station": session.emplacement.station.nom,
        "borne": session.emplacement.borne.nom,
        "borne_numero": session.emplacement.borne.numero,
        "mqtt_prefix": session.emplacement.borne.mqtt_prefix,
        "emplacement": session.emplacement.numero,
        "slot_id": _device_slot_id(device, session.emplacement),
        "start_time": session.start_time.isoformat(),
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "charge_state": session.charge_state,
        "charge_state_display": session.get_charge_state_display(),
        "status": "active" if session.end_time is None else "closed",
    }


def _close_charging_session(session, now=None):
    """Close an active charging session and mark its reservation as finished."""
    closed_at = now or timezone.now()
    updated = False
    if session.end_time is None:
        session.end_time = max(closed_at, session.start_time + timedelta(seconds=1))
        mark_stopped(session, now=closed_at, save=False)
        session.save(update_fields=["end_time", "charge_state", "charge_state_updated_at"])
        updated = True
    else:
        mark_stopped(session, now=closed_at)

    reservation = session.reservation
    if reservation.statut != "terminee":
        reservation.statut = "terminee"
        reservation.save(update_fields=["statut"])

    device = getattr(session.emplacement, "device", None)
    if device and device.status == DeviceStatus.CHARGING:
        device.status = DeviceStatus.ONLINE
        device.last_seen = closed_at
        device.save(update_fields=["status", "last_seen"])

    return updated


def _reservation_can_be_cancelled(reservation):
    """Return whether a reservation is still cancellable."""
    return reservation.statut not in {"annulee", "terminee"} and reservation.date_debut > timezone.now()


def _cancel_reservation(reservation):
    """Cancel a reservation when business rules still allow it."""
    if not _reservation_can_be_cancelled(reservation):
        return False
    reservation.statut = "annulee"
    reservation.save(update_fields=["statut"])
    return True


def _temporary_access_can_be_rotated(reservation):
    """Return whether a reservation can receive a new temporary credential."""
    return (
        reservation.auth_choice in {"qr", "code"}
        and reservation.statut not in {"annulee", "terminee"}
        and reservation.date_fin >= timezone.now()
    )


def _serialize_station(station):
    """Return public station fields used by catalog and admin screens."""
    return {
        "id_station": str(station.id_station),
        "nom": station.nom,
        "localisation_text": station.localisation_text,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "statut": station.statut,
    }


def _serialize_borne(borne):
    """Return physical cabinet fields with its parent station label."""
    return {
        "id_borne": str(borne.id_borne),
        "station": str(borne.station_id),
        "station_nom": borne.station.nom,
        "numero": borne.numero,
        "nom": borne.nom,
        "mqtt_prefix": borne.mqtt_prefix,
        "statut": borne.statut,
        "emplacements_count": borne.emplacements.count(),
    }


def _serialize_emplacement(emplacement):
    """Return charging bay details with the parent station label."""
    return {
        "id_emplacement": str(emplacement.id_emplacement),
        "station": str(emplacement.station_id),
        "station_nom": emplacement.station.nom,
        "borne": str(emplacement.borne_id),
        "borne_nom": emplacement.borne.nom,
        "borne_numero": emplacement.borne.numero,
        "numero": emplacement.numero,
        "statut": emplacement.statut,
        "lock_state": emplacement.lock_state,
    }


def _serialize_auth_method(method):
    """Return a safe authentication method payload without secret material."""
    display_value = method.display_value
    if method.type_auth and method.type_auth.libelle == "RFID":
        display_value = _mask_secret(method.display_value)
    return {
        "id_auth": str(method.id_auth),
        "type_auth": str(method.type_auth_id),
        "type_label": method.type_auth.libelle,
        "display_value": display_value,
        "expiration": method.expiration.isoformat() if method.expiration else None,
        "is_active": method.is_active,
        "created_at": method.created_at.isoformat() if method.created_at else None,
    }


def _serialize_admin_auth_method(method):
    """Return an admin-safe authentication method without exposing the raw badge value."""
    payload = _serialize_auth_method(method)
    payload["display_value"] = _mask_secret(method.display_value)
    return payload


def _serialize_maintenance(maintenance):
    """Return maintenance data used by technician and admin dashboards."""
    return {
        "id_maintenance": str(maintenance.id_maintenance),
        "station": str(maintenance.station_id),
        "station_nom": maintenance.station.nom,
        "technicien": str(maintenance.technicien_id),
        "type": maintenance.type,
        "description": maintenance.description,
        "status": maintenance.status,
        "date_planifiee": maintenance.date_planifiee.isoformat(),
        "date_realisee": maintenance.date_realisee.isoformat() if maintenance.date_realisee else None,
    }


def _serialize_technician(technician):
    """Return technician profile data with optional linked account metadata."""
    return {
        "id_technicien": str(technician.id_technicien),
        "utilisateur": str(technician.utilisateur_id) if technician.utilisateur_id else None,
        "utilisateur_pseudo": technician.utilisateur.pseudo if technician.utilisateur else None,
        "nom": technician.nom,
        "email": technician.email,
        "telephone": technician.telephone,
    }


def _active_station_assignments_prefetch():
    """Return the prefetch used to expose active technician station scopes."""
    return Prefetch(
        "station_assignments",
        queryset=TechnicienStation.objects.filter(is_active=True)
        .select_related("station")
        .order_by("station__nom"),
        to_attr="prefetched_active_station_assignments",
    )


def _user_is_technician(user):
    """Return whether the user has an associated technician profile."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if hasattr(user, "_technician_profile_cache"):
        return user._technician_profile_cache
    exists = Technicien.objects.filter(utilisateur_id=user.id_user).exists()
    user._technician_profile_cache = exists
    return exists


def _technician_for_user(user):
    """Return the technician profile linked to an authenticated account."""
    try:
        return user.technicien_profile
    except Technicien.DoesNotExist:
        return None


def _station_ids_for_technician(technicien):
    """Return active station identifiers assigned to a technician."""
    return list(
        TechnicienStation.objects.filter(technicien=technicien, is_active=True)
        .order_by("station__nom")
        .values_list("station_id", flat=True)
    )


def _sync_technician_station_scope(technician, station_scope):
    """Synchronize active station assignments from the technician edit form."""
    if station_scope is None:
        return

    requested_ids = {str(station_id) for station_id in station_scope}
    assignments = {
        str(assignment.station_id): assignment
        for assignment in TechnicienStation.objects.filter(technicien=technician)
    }

    for station_id, assignment in assignments.items():
        should_be_active = station_id in requested_ids
        if assignment.is_active != should_be_active:
            assignment.is_active = should_be_active
            assignment.save(update_fields=["is_active"])

    missing_ids = requested_ids - set(assignments)
    TechnicienStation.objects.bulk_create(
        [
            TechnicienStation(
                technicien=technician,
                station_id=station_id,
                role="intervenant",
                is_active=True,
            )
            for station_id in missing_ids
        ]
    )


def _technician_can_manage_alert(user, alert):
    """Return the technician profile allowed to operate on an alert."""
    if user.is_staff:
        return _technician_for_user(user), None

    technicien = _technician_for_user(user)
    if technicien is None:
        return None, Response(
            {"detail": "Aucun profil technicien associé à ce compte."},
            status=status.HTTP_404_NOT_FOUND,
        )

    station_id = alert_station_id(alert)
    if station_id is None:
        return None, Response(
            {"detail": "Impossible de rattacher cette alerte a une station."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if station_id not in set(_station_ids_for_technician(technicien)):
        return None, Response(
            {"detail": "Cette alerte ne fait pas partie de vos stations."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return technicien, None


def _generate_reservation_code():
    """Generate a short unique reservation reference code."""
    for _ in range(20):
        code = "".join(secrets.choice(KEYPAD_CODE_ALPHABET) for _ in range(RESERVATION_CODE_LENGTH))
        if not Reservation.objects.filter(reference_code=code).exists():
            return code
    raise RuntimeError("Impossible de générer un code de réservation unique.")


def _rfid_link_cache_key(code):
    """Return the cache key for a temporary RFID association code."""
    return f"rfid-link:{code}"


def _mobile_session_cache_key(token):
    """Return the cache key for a short kiosk/mobile pairing session."""
    return f"mobile-session:{token}"


def _generate_rfid_link_code():
    """Generate a short one-use code that can be typed on the kiosk."""
    for _ in range(20):
        code = "".join(secrets.choice(KEYPAD_CODE_ALPHABET) for _ in range(RFID_LINK_CODE_LENGTH))
        if cache.get(_rfid_link_cache_key(code)) is None:
            return code
    raise RuntimeError("Impossible de générer un code RFID temporaire unique.")


def _generate_mobile_session_token():
    """Generate a URL-safe token for a kiosk/mobile pairing session."""
    for _attempt in range(20):
        token = secrets.token_urlsafe(MOBILE_SESSION_TOKEN_BYTES)
        if cache.get(_mobile_session_cache_key(token)) is None:
            return token
    raise RuntimeError("Impossible de générer une session mobile unique.")


def _normalize_public_frontend_origin(value):
    """Return a safe public frontend origin supplied by the kiosk, or an empty string."""
    origin = str(value or "").strip().rstrip("/")
    if not origin:
        return ""

    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc or parsed.username or parsed.password:
        return ""
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        return ""
    return origin


def _mobile_session_url(token, frontend_origin=""):
    """Return the PWA URL opened by a phone for one kiosk pairing session."""
    base_url = _normalize_public_frontend_origin(frontend_origin) or settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base_url}/mobile-session.html?token={token}"


def _store_mobile_session(payload):
    """Persist a mobile pairing payload until its absolute expiry."""
    expires_at = datetime.fromisoformat(payload["expires_at"])
    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
    ttl = max(1, int((expires_at - timezone.now()).total_seconds()))
    cache.set(_mobile_session_cache_key(payload["token"]), payload, timeout=ttl)


def _get_mobile_session_payload(token):
    """Return a cached mobile pairing session or None when it expired."""
    token = (token or "").strip()
    if not token:
        return None
    return cache.get(_mobile_session_cache_key(token))


def _serialize_mobile_session(payload):
    """Return public metadata about a kiosk/mobile pairing session."""
    expires_at = datetime.fromisoformat(payload["expires_at"])
    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
    return {
        "token": payload["token"],
        "status": payload.get("status", "pending"),
        "station_id": payload.get("station_id"),
        "station_nom": payload.get("station_nom"),
        "borne_id": payload.get("borne_id"),
        "borne_nom": payload.get("borne_nom"),
        "borne_numero": payload.get("borne_numero"),
        "created_at": payload.get("created_at"),
        "expires_at": payload.get("expires_at"),
        "expires_in": max(0, int((expires_at - timezone.now()).total_seconds())),
    }


def _generate_access_nonce():
    """Generate a public nonce used to derive a temporary access secret."""
    return secrets.token_urlsafe(18)


def _digest_to_keypad_code(digest, length=TEMPORARY_CODE_LENGTH):
    """Convert digest bytes to a code that can be typed on the matrix keypad."""
    code = []
    source = digest
    round_index = 0
    max_accepted = (256 // len(KEYPAD_CODE_ALPHABET)) * len(KEYPAD_CODE_ALPHABET)

    while len(code) < length:
        for byte in source:
            if byte >= max_accepted:
                continue
            code.append(KEYPAD_CODE_ALPHABET[byte % len(KEYPAD_CODE_ALPHABET)])
            if len(code) == length:
                break
        if len(code) < length:
            round_index += 1
            source = hashlib.sha256(digest + round_index.to_bytes(2, "big")).digest()

    return "".join(code)


def _derive_temporary_access_secret(auth_method, auth_mode, reservation_code):
    """Derive a stable temporary secret without storing the clear value."""
    metadata = auth_method.metadata or {}
    nonce = metadata.get("access_nonce")
    if not nonce:
        return None

    material = "|".join(
        [
            str(auth_method.id_auth),
            str(reservation_code or ""),
            str(auth_mode or "").lower(),
            str(nonce),
        ]
    ).encode("utf-8")
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), material, hashlib.sha256).digest()
    if str(auth_mode).lower() == "code":
        return _digest_to_keypad_code(digest)

    token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:24]
    return f"{str(auth_mode).upper()}-{token}"


def _mask_secret(secret):
    """Return a display-safe hint for a secret value."""
    if not secret:
        return ""
    return f"****{secret[-4:]}"


def _sms_access_is_locked(auth_method):
    """Return whether the SMS code is locked after too many failed attempts."""
    if not auth_method:
        return False
    metadata = auth_method.metadata or {}
    attempts = int(metadata.get("sms_failed_attempts") or 0)
    return bool(metadata.get("sms_locked_at")) or attempts >= SMS_ACCESS_CODE_MAX_ATTEMPTS


def _record_sms_access_failure(auth_method):
    """Increment failed SMS-code attempts and lock the credential if needed."""
    metadata = dict(auth_method.metadata or {})
    failed_attempts = int(metadata.get("sms_failed_attempts") or 0) + 1
    metadata["sms_failed_attempts"] = failed_attempts
    metadata["sms_last_failed_at"] = timezone.now().isoformat()
    metadata["sms_max_attempts"] = SMS_ACCESS_CODE_MAX_ATTEMPTS
    update_fields = ["metadata"]
    if failed_attempts >= SMS_ACCESS_CODE_MAX_ATTEMPTS:
        metadata["sms_locked_at"] = timezone.now().isoformat()
        metadata["sms_locked_reason"] = "too_many_attempts"
        auth_method.is_active = False
        update_fields.append("is_active")
    auth_method.metadata = metadata
    auth_method.save(update_fields=update_fields)
    return failed_attempts >= SMS_ACCESS_CODE_MAX_ATTEMPTS


def _reset_sms_access_failures(auth_method):
    """Clear failed-attempt metadata after a valid SMS code entry."""
    if not auth_method:
        return
    metadata = dict(auth_method.metadata or {})
    changed = False
    for key in (
        "sms_failed_attempts",
        "sms_last_failed_at",
        "sms_locked_at",
        "sms_locked_reason",
    ):
        if key in metadata:
            metadata.pop(key, None)
            changed = True
    if changed:
        auth_method.metadata = metadata
        auth_method.save(update_fields=["metadata"])


def _user_phone_number(user):
    """Return the phone number stored on a user's profile."""
    profile = getattr(user, "profil", None)
    return (getattr(profile, "telephone", "") or "").strip()


def _user_phone_is_verified(user):
    """Return whether the user's phone number is marked as verified."""
    profile = getattr(user, "profil", None)
    return bool(getattr(profile, "telephone_verifie", False))


def _build_sms_access_message(reservation, access_value):
    """Build the transactional SMS sent for a temporary code reservation."""
    sender = getattr(settings, "SMS_SENDER_NAME", "Station")
    return (
        f"{sender}: votre code de recharge est {access_value}. "
        f"Code réservation: {reservation.reference_code}. "
        f"Valable jusqu'au {timezone.localtime(reservation.date_fin).strftime('%d/%m/%Y %H:%M')}."
    )


def _sms_resend_wait_seconds(auth_method):
    """Return remaining cooldown seconds before another SMS can be sent."""
    cooldown = getattr(settings, "SMS_RESEND_COOLDOWN_SECONDS", 60)
    if cooldown <= 0 or auth_method is None:
        return 0

    last_sent = parse_datetime((auth_method.metadata or {}).get("sms_last_sent_at", ""))
    if last_sent is None:
        return 0
    if timezone.is_naive(last_sent):
        last_sent = timezone.make_aware(last_sent, timezone=datetime_timezone.utc)
    elapsed = (timezone.now() - last_sent).total_seconds()
    return max(0, int(cooldown - elapsed))


def _build_qr_payload(reservation_code, token):
    """Encode reservation access data into the QR payload format."""
    return json.dumps(
        {
            "v": 1,
            "type": "reservation_access",
            "reservation": reservation_code,
            "token": token,
        },
        separators=(",", ":"),
    )


def _parse_qr_payload(raw_value):
    """Parse supported QR payload formats into reservation code and token."""
    value = (raw_value or "").strip()
    if not value:
        return None

    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict) and payload.get("type") == "reservation_access":
        reservation_code = str(payload.get("reservation") or "").strip().upper()
        token = str(payload.get("token") or "").strip()
        if reservation_code and token:
            return {"reservation_code": reservation_code, "token": token}

    if value.startswith("MVCHARGE|"):
        parts = value.split("|", 3)
        if len(parts) == 4 and parts[1] == "v1":
            return {"reservation_code": parts[2].strip().upper(), "token": parts[3].strip()}

    return None


def _build_qr_svg(payload):
    """Render a QR code SVG for a reservation access payload."""
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        return None

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(image_factory=SvgPathImage)
    buffer = BytesIO()
    image.save(buffer)
    svg = buffer.getvalue().decode("utf-8")
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].lstrip()
    pictogram = """
<svg x="41%" y="41%" width="18%" height="18%" viewBox="0 0 64 64" role="img" aria-label="Accès sécurisé Métropole Verte">
  <rect x="2" y="2" width="60" height="60" rx="12" fill="#ffffff"/>
  <path d="M32 9c-9 9-15 18-15 27 0 10 7 17 15 17s15-7 15-17C47 27 41 18 32 9Z" fill="#1f8f55"/>
  <path d="M22 36c8-1 15-6 21-17-1 16-8 26-21 30" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
</svg>
"""
    return svg.replace("</svg>", f"{pictogram}</svg>")


def _temporary_auth_metadata(auth_mode, expiration, reservation_code, display_value, access_nonce=None):
    """Build metadata stored alongside a generated temporary credential."""
    metadata = {
        "version": 1,
        "secret_storage": "derived_sha256",
        "access_nonce": access_nonce or _generate_access_nonce(),
        "token_hint": display_value,
        "expires_at": expiration.isoformat(),
    }
    if auth_mode == "code":
        metadata.update(
            {
                "delivery_channel": "sms",
                "code_policy": sms_access_code_policy_payload(),
            }
        )
    if auth_mode == "qr":
        metadata.update(
            {
                "payload_type": "reservation_access",
                "payload_encoding": "json",
                "reservation_code": reservation_code,
            }
        )
    return metadata


def _build_access_payload(auth_mode, access_value, auth_method, expiration):
    """Return the one-time access payload shown after reservation creation."""
    payload = {
        "mode": auth_mode,
        "display_value": auth_method.display_value if auth_method else "",
        "expires_at": expiration.isoformat(),
    }
    if auth_mode == "qr":
        payload["value"] = access_value
        payload["qr_svg"] = _build_qr_svg(access_value)
        payload["format"] = "reservation_access_v1"
    if auth_mode == "code":
        metadata = auth_method.metadata if auth_method else {}
        payload["delivery_channel"] = "sms"
        payload["recipient_hint"] = metadata.get("sms_recipient_hint", "")
        payload["sent_at"] = metadata.get("sms_last_sent_at", "")
        payload["code_policy"] = metadata.get("code_policy") or sms_access_code_policy_payload()
    return payload


def _send_reservation_sms_code(request, reservation, auth_method, access_value):
    """Send the temporary reservation code by SMS and update audit metadata."""
    phone_number = _user_phone_number(reservation.utilisateur)
    if not phone_number:
        return None, Response(
            {"telephone": "Un numéro de téléphone est obligatoire pour recevoir un code SMS."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if getattr(settings, "SMS_REQUIRE_VERIFIED_PHONE", False) and not _user_phone_is_verified(reservation.utilisateur):
        return None, Response(
            {"telephone": "Le numéro de téléphone doit être vérifié avant l'envoi d'un code SMS."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    wait_seconds = _sms_resend_wait_seconds(auth_method)
    if wait_seconds > 0:
        return None, Response(
            {
                "detail": "Un code SMS a déjà été envoyé récemment.",
                "retry_after_seconds": wait_seconds,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        delivery = send_sms(
            phone_number,
            _build_sms_access_message(reservation, access_value),
        )
    except SmsDeliveryError as error:
        logger.warning("SMS delivery failed for reservation %s: %s", reservation.id_reservation, error)
        return None, Response({"detail": "Envoi SMS temporairement indisponible."}, status=status.HTTP_502_BAD_GATEWAY)

    sent_at = timezone.now()
    recipient_hint = mask_phone_number(phone_number)
    auth_method.metadata = {
        **(auth_method.metadata or {}),
        "delivery_channel": "sms",
        "sms_last_sent_at": sent_at.isoformat(),
        "sms_recipient_hint": recipient_hint,
        "sms_backend": delivery.backend,
        "sms_message_id": delivery.message_id,
    }
    auth_method.save(update_fields=["metadata"])
    _log_security_event(
        request,
        reservation.utilisateur,
        f"user:{reservation.utilisateur.pseudo}:sms_access_code_sent:{reservation.reference_code}",
    )
    return (
        {
            "sent_at": sent_at,
            "recipient_hint": recipient_hint,
            "backend": delivery.backend,
        },
        None,
    )


def _schedule_reservation_qr_email(request, reservation, auth_method, access_payload):
    """Send the reservation QR email after the reservation transaction commits."""
    if not getattr(settings, "RESERVATION_QR_EMAIL_ENABLED", True):
        return

    def _send_after_commit():
        try:
            sent_count = send_reservation_qr_email(reservation, access_payload)
        except Exception as error:  # pragma: no cover - depends on SMTP availability
            logger.warning("QR email delivery failed for reservation %s: %s", reservation.id_reservation, error)
            return
        if not sent_count:
            return
        sent_at = timezone.now()
        auth_method.metadata = {
            **(auth_method.metadata or {}),
            "delivery_channel": "email",
            "qr_email_last_sent_at": sent_at.isoformat(),
            "qr_email_recipient": reservation.utilisateur.email,
        }
        auth_method.save(update_fields=["metadata"])
        _log_security_event(
            request,
            reservation.utilisateur,
            f"user:{reservation.utilisateur.pseudo}:qr_access_email_sent:{reservation.reference_code}",
        )

    transaction.on_commit(_send_after_commit)


def _create_temporary_auth(user, auth_mode, expiration, reservation_code):
    """Create a temporary QR or code credential for a reservation."""
    type_auth = _get_type_auth(auth_mode)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur="pending",
        metadata=_temporary_auth_metadata(auth_mode, expiration, reservation_code, ""),
        expiration=expiration,
    )
    clear_value = _derive_temporary_access_secret(auth_method, auth_mode, reservation_code)
    display_value = _mask_secret(clear_value)
    auth_method.hash_valeur = _hash_secret(clear_value)
    auth_method.display_value = display_value
    auth_method.metadata = _temporary_auth_metadata(
        auth_mode,
        expiration,
        reservation_code,
        display_value,
        access_nonce=auth_method.metadata.get("access_nonce"),
    )
    auth_method.save(update_fields=["hash_valeur", "display_value", "metadata"])
    if auth_mode == "qr":
        return auth_method, _build_qr_payload(reservation_code, clear_value)
    return auth_method, clear_value


def _refresh_temporary_auth(reservation):
    """Rotate the temporary credential attached to a reservation."""
    auth_mode = reservation.auth_choice
    auth_method = reservation.authentification
    if auth_method is None:
        auth_method = Authentification(
            utilisateur=reservation.utilisateur,
            type_auth=_get_type_auth(auth_mode),
        )

    access_nonce = _generate_access_nonce()
    auth_method.metadata = _temporary_auth_metadata(
        auth_mode,
        reservation.date_fin,
        reservation.reference_code,
        "",
        access_nonce=access_nonce,
    )
    clear_value = _derive_temporary_access_secret(auth_method, auth_mode, reservation.reference_code)
    display_value = _mask_secret(clear_value)
    auth_method.type_auth = _get_type_auth(auth_mode)
    auth_method.hash_valeur = _hash_secret(clear_value)
    auth_method.display_value = display_value
    auth_method.metadata = _temporary_auth_metadata(
        auth_mode,
        reservation.date_fin,
        reservation.reference_code,
        display_value,
        access_nonce=access_nonce,
    )
    auth_method.expiration = reservation.date_fin
    auth_method.is_active = True
    auth_method.save()

    if reservation.authentification_id != auth_method.id_auth:
        reservation.authentification = auth_method
        reservation.save(update_fields=["authentification"])

    if auth_mode == "qr":
        return auth_method, _build_qr_payload(reservation.reference_code, clear_value)
    return auth_method, clear_value


def _get_temporary_access_value(reservation):
    """Return the current temporary access value, deriving it when possible."""
    auth_method = reservation.authentification
    if auth_method is None or not auth_method.is_active:
        return None, None

    clear_value = _derive_temporary_access_secret(
        auth_method,
        reservation.auth_choice,
        reservation.reference_code,
    )
    if not clear_value:
        return None, None

    expected_hash = _hash_secret(clear_value)
    if auth_method.hash_valeur != expected_hash:
        auth_method.hash_valeur = expected_hash
        auth_method.display_value = _mask_secret(clear_value)
        auth_method.metadata = {
            **(auth_method.metadata or {}),
            "token_hint": auth_method.display_value,
        }
        auth_method.save(update_fields=["hash_valeur", "display_value", "metadata"])

    if reservation.auth_choice == "qr":
        return auth_method, _build_qr_payload(reservation.reference_code, clear_value)
    return auth_method, clear_value


def _get_reservation_session(reservation):
    """Return the charging session linked to a reservation when it exists."""
    try:
        return reservation.session
    except ChargingSession.DoesNotExist:
        return None


def _start_grace_delta():
    """Return the allowed early-arrival margin for a reservation."""
    return timedelta(minutes=RESERVATION_START_GRACE_MINUTES)


def _end_grace_delta():
    """Return the allowed late-arrival margin for a reservation."""
    return timedelta(minutes=RESERVATION_END_GRACE_MINUTES)


def _terminal_reservation_queryset():
    """Return reservations with the related data needed by terminal flows."""
    return Reservation.objects.select_related(
        "utilisateur",
        "emplacement",
        "emplacement__station",
        "emplacement__borne",
        "authentification",
        "authentification__type_auth",
        "session",
    )


def _active_rfid_reservations_for_auth(auth_method, now):
    """Return active or startable reservations that match a saved RFID badge."""
    start_grace = _start_grace_delta()
    end_grace = _end_grace_delta()
    return list(
        _terminal_reservation_queryset()
        .filter(
            Q(date_fin__gte=now - end_grace) | Q(session__end_time__isnull=True, session__isnull=False),
            utilisateur=auth_method.utilisateur,
            authentification=auth_method,
            auth_choice="rfid",
            statut__in=["confirmee", "active"],
            date_debut__lte=now + start_grace,
        )
        .order_by("date_debut", "id_reservation")[:2]
    )


def _startable_user_reservations(user, now):
    """Return reservations that can be started from a kiosk soon or now."""
    start_grace = _start_grace_delta()
    end_grace = _end_grace_delta()
    return list(
        _terminal_reservation_queryset()
        .filter(
            Q(date_fin__gte=now - end_grace) | Q(session__end_time__isnull=True, session__isnull=False),
            utilisateur=user,
            statut__in=["confirmee", "active"],
            date_debut__lte=now + start_grace,
        )
        .order_by("date_debut", "id_reservation")
    )


def _serialize_offline_cached_reservation(reservation):
    """Return the minimal secret-free payload cached by a kiosk for offline checks."""
    auth_method = reservation.authentification
    device = getattr(reservation.emplacement, "device", None)
    return {
        "id_reservation": str(reservation.id_reservation),
        "reference_code": reservation.reference_code,
        "station_id": str(reservation.emplacement.station_id),
        "station_nom": reservation.emplacement.station.nom,
        "borne_id": str(reservation.emplacement.borne_id),
        "borne_nom": reservation.emplacement.borne.nom,
        "borne_numero": reservation.emplacement.borne.numero,
        "mqtt_prefix": reservation.emplacement.borne.mqtt_prefix,
        "emplacement_id": str(reservation.emplacement_id),
        "emplacement_numero": reservation.emplacement.numero,
        "slot_id": _device_slot_id(device, reservation.emplacement),
        "auth_mode": reservation.auth_choice,
        "auth_hash": auth_method.hash_valeur if auth_method else "",
        "auth_expires_at": auth_method.expiration.isoformat() if auth_method and auth_method.expiration else None,
        "date_debut": reservation.date_debut.isoformat(),
        "date_fin": reservation.date_fin.isoformat(),
        "statut": reservation.statut,
    }


def _offline_event_timestamp(value):
    """Parse a kiosk event timestamp, falling back to server time."""
    if not value:
        return timezone.now()
    parsed = parse_datetime(str(value))
    if parsed is None:
        return timezone.now()
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)
    return parsed


def _reconcile_offline_session_started(request, event, station_id, borne_id=""):
    """Create or recover the backend session for one accepted offline start event."""
    reservation_id = event.get("reservation_id") or (event.get("payload") or {}).get("reservation", {}).get("id_reservation")
    borne_id = (
        borne_id
        or (event.get("payload") or {}).get("borne_id")
        or (event.get("payload") or {}).get("reservation", {}).get("borne_id")
    )
    if not reservation_id:
        return None, "reservation_id manquant."

    reservation = _terminal_reservation_queryset().filter(id_reservation=reservation_id).first()
    if reservation is None:
        return None, "Réservation introuvable."

    if station_id and str(reservation.emplacement.station_id) != station_id:
        return None, "Réservation associée à une autre station."
    if borne_id and str(reservation.emplacement.borne_id) != str(borne_id):
        return None, "Réservation associée à une autre borne."

    start_time = _offline_event_timestamp(event.get("created_at"))
    with transaction.atomic():
        session, created = ChargingSession.objects.get_or_create(
            reservation=reservation,
            defaults={
                "emplacement": reservation.emplacement,
                "start_time": start_time,
            },
        )
        try:
            mark_access_validated(session, now=start_time)
        except ChargeSessionStateError:
            return None, CHARGE_SESSION_STATE_ERROR_DETAIL
        if reservation.statut != "active":
            reservation.statut = "active"
            reservation.save(update_fields=["statut"])

        auth_method = reservation.authentification
        if created and auth_method and reservation.auth_choice in {"qr", "code"}:
            auth_method.expiration = session.start_time + timedelta(minutes=DEFAULT_SESSION_MAX_MINUTES)
            auth_method.metadata = {
                **(auth_method.metadata or {}),
                "session_started_at": session.start_time.isoformat(),
                "session_max_minutes": DEFAULT_SESSION_MAX_MINUTES,
                "offline_event_id": event.get("id"),
                "offline_session_id": event.get("session_id"),
            }
            auth_method.save(update_fields=["expiration", "metadata"])

    JournalSecurite.objects.create(
        utilisateur=reservation.utilisateur,
        action=f"terminal:offline_session_synced:{reservation.reference_code}:{event.get('id')}",
        ip=_client_ip(request),
        statut="success",
    )
    return {
        "event_id": event.get("id"),
        "reservation_id": str(reservation.id_reservation),
        "session_id": str(session.id_session),
        "session_created": created,
    }, None


def _resolve_direct_rfid_reservation(auth_value, now):
    """Resolve a badge UID directly to one active reservation."""
    type_auth = _get_type_auth("RFID")
    matching_auth_methods = list(
        Authentification.objects.select_related("utilisateur", "type_auth")
        .filter(
            type_auth=type_auth,
            hash_valeur=_hash_secret(auth_value),
            is_active=True,
        )[:2]
    )

    if not matching_auth_methods:
        return None, None, Response({"detail": "Badge RFID inconnu."}, status=status.HTTP_401_UNAUTHORIZED)

    if len(matching_auth_methods) > 1:
        return None, None, Response(
            {"detail": "Ce badge RFID est associé à plusieurs comptes."},
            status=status.HTTP_409_CONFLICT,
        )

    auth_method = matching_auth_methods[0]
    if auth_method.expiration and auth_method.expiration < now:
        return None, None, Response({"detail": "Le badge RFID est expiré."}, status=status.HTTP_400_BAD_REQUEST)

    reservations = _active_rfid_reservations_for_auth(auth_method, now)
    if not reservations:
        return None, None, Response(
            {"detail": "Aucune réservation active pour ce badge RFID."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if len(reservations) > 1:
        return None, None, Response(
            {
                "detail": "Plusieurs réservations actives correspondent à ce badge RFID.",
                "reservations": [_serialize_reservation(reservation) for reservation in reservations],
            },
            status=status.HTTP_409_CONFLICT,
        )

    return auth_method, reservations[0], None


def _reservation_overlaps(emplacement, date_debut, date_fin):
    """Return whether a charging bay is already booked in the paid window."""
    return Reservation.objects.filter(
        emplacement=emplacement,
        date_debut__lt=date_fin,
        date_fin__gt=date_debut,
        statut__in=["confirmee", "active", "en_attente"],
    ).exists()


def _session_start_conflict_response(reservation, now):
    """Return a conflict response if another booking still owns the bay."""
    active_session = (
        ChargingSession.objects.select_related("reservation")
        .filter(emplacement=reservation.emplacement, end_time__isnull=True)
        .exclude(reservation=reservation)
        .first()
    )
    if active_session:
        return Response(
            {"detail": "L'emplacement est déjà utilisé par une autre session de charge."},
            status=status.HTTP_409_CONFLICT,
        )

    if now < reservation.date_debut:
        paid_window_owner = (
            Reservation.objects.filter(
                emplacement=reservation.emplacement,
                date_debut__lte=now,
                date_fin__gt=now,
                statut__in=["confirmee", "active", "en_attente"],
            )
            .exclude(id_reservation=reservation.id_reservation)
            .first()
        )
        if paid_window_owner:
            return Response(
                {"detail": "L'emplacement est encore réservé par le créneau précédent."},
                status=status.HTTP_409_CONFLICT,
            )

    return None


def _available_emplacements(station, date_debut, date_fin):
    """Return available charging bays for a station and paid reservation window."""
    overlapping_reservations = Reservation.objects.filter(
        emplacement=OuterRef("pk"),
        date_debut__lt=date_fin,
        date_fin__gt=date_debut,
        statut__in=["confirmee", "active", "en_attente"],
    )
    return list(
        Emplacement.objects.filter(station=station)
        .select_related("station", "borne")
        .annotate(has_overlap=Exists(overlapping_reservations))
        .filter(has_overlap=False)
        .order_by("borne__numero", "numero")
    )


def _round_to_thirty_minutes(dt):
    """Return whether a datetime is aligned to a 30-minute boundary."""
    if dt.minute % RESERVATION_STEP_MINUTES != 0 or dt.second != 0 or dt.microsecond != 0:
        return False
    return True


def _duration_is_valid(date_debut, date_fin):
    """Return whether the requested reservation duration is supported."""
    return reservation_duration_is_allowed(date_debut, date_fin)


@_schema(
    "Vérifier la disponibilité d'un pseudo ou d'un email",
    parameters=[
        OpenApiParameter("pseudo", OpenApiTypes.STR, OpenApiParameter.QUERY),
        OpenApiParameter("email", OpenApiTypes.STR, OpenApiParameter.QUERY),
    ],
    tags=["Authentification"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationRateThrottle])
def register_availability(request):
    """Report whether a pseudo or email can be used for registration."""
    pseudo = (request.query_params.get("pseudo") or "").strip()
    email = (request.query_params.get("email") or "").strip()
    response = {}

    if pseudo:
        pseudo_exists = User.objects.filter(pseudo__iexact=pseudo).exists()
        response["pseudo"] = {
            "available": not pseudo_exists,
            "message": "Ce pseudo est déjà utilisé." if pseudo_exists else "Ce pseudo est disponible.",
        }

    if email:
        try:
            validate_email(email)
        except ValidationError:
            response["email"] = {
                "available": False,
                "valid_format": False,
                "message": "Le format de l’adresse email est invalide.",
            }
        else:
            email_exists = User.objects.filter(email__iexact=email).exists()
            response["email"] = {
                "available": not email_exists,
                "valid_format": True,
                "message": "Cette adresse email est déjà utilisée." if email_exists else "Cette adresse email est disponible.",
            }

    return Response(response)


@_schema("Créer un compte utilisateur", request=RegisterSerializer, tags=["Authentification"])
@api_view(["POST"])
@throttle_classes([RegistrationRateThrottle])
def register(request):
    """Create a user account and return an authenticated JWT session."""
    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        response = Response(
            {
                "message": "Utilisateur créé",
                "user": _serialize_user(user),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )
        return _set_refresh_cookie(response, refresh)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@_schema("Connecter un utilisateur", request=OpenApiTypes.OBJECT, tags=["Authentification"])
@api_view(["POST"])
@throttle_classes([LoginRateThrottle])
def login(request):
    """Authenticate a user and issue access and refresh tokens."""
    identifiant = (
        request.data.get("identifiant")
        or request.data.get("username")
        or request.data.get("email")
    )
    password = request.data.get("password")

    user = authenticate(request, identifiant=identifiant, password=password)

    if user is not None:
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(user)

        response = Response(
            {
                "access": str(refresh.access_token),
                "user": _serialize_user(user),
            }
        )
        return _set_refresh_cookie(response, refresh)

    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@_schema("Rafraîchir le jeton d'accès", request=OpenApiTypes.OBJECT, tags=["Authentification"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TokenRefreshRateThrottle])
def refresh_token(request):
    """Issue a new access token from the HttpOnly refresh cookie."""
    refresh = request.data.get("refresh") or request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    if not refresh:
        return Response({"detail": "Refresh token absent."}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = TokenRefreshSerializer(data={"refresh": refresh})
    serializer.is_valid(raise_exception=True)
    response = Response({"access": serializer.validated_data["access"]})
    rotated_refresh = serializer.validated_data.get("refresh")
    if rotated_refresh:
        _set_refresh_cookie(response, rotated_refresh)
    return response


@_schema("Déconnecter l'utilisateur", tags=["Authentification"])
@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    """Clear the HttpOnly refresh cookie used by the browser session."""
    return _clear_refresh_cookie(Response({"message": "Déconnexion effectuée."}))


@_schema("Lire le profil de l'utilisateur connecté", tags=["Compte"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Return the current authenticated user's profile summary."""
    profile = _get_or_create_profile(request.user)
    return Response(
        {
            "user": _serialize_user(request.user),
            "profile": {
                "nom": profile.nom,
            },
        }
    )


@_schema("Lire, modifier ou supprimer le profil", request=ProfileSerializer, tags=["Compte"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def profile(request):
    """Read, update or delete the authenticated user's account profile."""
    user = request.user
    profile = _get_or_create_profile(user)

    if request.method == "GET":
        return Response(
            {
                "user": _serialize_user(user),
                "profile": {"nom": profile.nom},
            }
        )

    if request.method == "PATCH":
        serializer = ProfileSerializer(instance=user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        profile.refresh_from_db()
        user.refresh_from_db()
        return Response(
            {
                "message": "Profil mis a jour",
                "user": _serialize_user(user),
                "profile": {"nom": profile.nom},
            }
        )

    if request.method == "DELETE":
        user_id = user.id_user
        user.delete()
        return Response(
            {
                "message": "Compte supprime",
                "user_id": str(user_id),
            },
            status=status.HTTP_200_OK,
        )

    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@_schema("Lire ou modifier les consentements", request=ConsentPreferenceSerializer, tags=["Compte"])
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def consentements(request):
    """Expose consent history and append editable preference changes."""
    user = request.user

    if request.method == "GET":
        return Response(_serialize_user_consents(user))

    serializer = ConsentPreferenceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    target_status = "accepte" if serializer.validated_data["notifications_accepted"] else "refuse"
    latest = (
        user.consentements.filter(type="notifications")
        .order_by("-date_consentement")
        .first()
    )
    changed = latest is None or latest.statut != target_status

    if changed:
        Consentement.objects.create(
            utilisateur=user,
            type="notifications",
            statut=target_status,
        )

    return Response(
        {
            "message": "Consentements mis a jour" if changed else "Consentements inchanges",
            **_serialize_user_consents(user),
        }
    )


@_schema("Changer le mot de passe", request=PasswordChangeSerializer, tags=["Compte"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change the authenticated user's password after current-password check."""
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    if not user.check_password(serializer.validated_data["current_password"]):
        return Response(
            {"current_password": "Mot de passe actuel incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    return Response({"message": "Mot de passe mis a jour"})


@_schema("Exporter les données du compte", tags=["Compte"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_account(request):
    """Export the authenticated user's account, reservations and audit history."""
    user = request.user
    profile = _get_or_create_profile(user)
    reservations = user.reservations.select_related("emplacement", "emplacement__station", "emplacement__borne").order_by("-date_debut")
    sessions = ChargingSession.objects.filter(reservation__utilisateur=user).select_related(
        "reservation", "emplacement", "emplacement__station", "emplacement__borne"
    ).order_by("-start_time")

    payload = {
        "user": {
            **_serialize_user(user),
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "profile": {"nom": profile.nom},
        "reservations": [_serialize_reservation(reservation) for reservation in reservations],
        "sessions": [_serialize_session(session) for session in sessions],
        "consentements": [
            {
                "id": str(consentement.id_consentement),
                "type": consentement.type,
                "statut": consentement.statut,
                "date_consentement": consentement.date_consentement.isoformat(),
            }
            for consentement in user.consentements.all().order_by("-date_consentement")
        ],
        "journaux_securite": [
            {
                "id": str(log.id_log),
                "action": log.action,
                "ip": log.ip,
                "statut": log.statut,
                "date_action": log.date_action.isoformat(),
            }
            for log in user.journaux_securite.all().order_by("-date_action")
        ],
    }

    return Response(payload)


@_schema("Lire le tableau de bord utilisateur", tags=["Tableau de bord"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """Return the authenticated user's dashboard metrics and recent activity."""
    sessions_qs = (
        ChargingSession.objects.filter(reservation__utilisateur=request.user)
        .select_related("reservation", "emplacement", "emplacement__station", "emplacement__borne")
        .order_by("-start_time")
    )

    reservations_qs = (
        Reservation.objects.filter(utilisateur=request.user)
        .select_related("emplacement", "emplacement__station", "emplacement__borne", "authentification", "authentification__type_auth")
        .order_by("-date_debut")
    )

    active_session = sessions_qs.filter(end_time__isnull=True).first()

    past_sessions = sessions_qs.filter(end_time__isnull=False)
    now = timezone.now()
    upcoming_reservations = reservations_qs.filter(date_debut__gte=now).exclude(statut="annulee")
    archived_reservations = reservations_qs.filter(date_debut__lt=now) | reservations_qs.filter(statut="annulee")
    recent_reservations = archived_reservations.distinct().order_by("-date_debut")[:5]

    return Response(
        {
            "user": _serialize_user(request.user),
            "stats": {
                "sessions_total": sessions_qs.count(),
                "active_sessions": sessions_qs.filter(end_time__isnull=True).count(),
                "past_sessions": past_sessions.count(),
                "reservations_total": reservations_qs.count(),
                "reservations_upcoming": upcoming_reservations.count(),
            },
            "active_session": _serialize_session(active_session) if active_session else None,
            "recharge_history": [
                _serialize_session(session)
                for session in sessions_qs[:5]
            ],
            "reservations_history": [
                ReservationSerializer(reservation).data
                for reservation in recent_reservations
            ],
            "upcoming_reservations": [
                ReservationSerializer(reservation).data
                for reservation in upcoming_reservations[:5]
            ],
        }
    )


@_schema("Lire la synthese administrateur", tags=["Administration"])
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_overview(request):
    """Return aggregate administration metrics and recent records."""
    return Response(
        {
            "stats": {
                "users_total": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "stations_total": Station.objects.count(),
                "bornes_total": Borne.objects.count(),
                "emplacements_total": Emplacement.objects.count(),
                "reservations_total": Reservation.objects.count(),
                "reservations_upcoming": Reservation.objects.filter(date_debut__gte=timezone.now()).exclude(statut="annulee").count(),
                "reservations_cancelled": Reservation.objects.filter(statut="annulee").count(),
                "sessions_total": ChargingSession.objects.count(),
                "sessions_active": ChargingSession.objects.filter(end_time__isnull=True).count(),
                "sessions_archived": ChargingSession.objects.filter(end_time__isnull=False).count(),
            },
            "recent_users": [
                _serialize_user(user)
                for user in User.objects.select_related("profil", "technicien_profile").order_by("-date_joined")[:5]
            ],
            "recent_stations": [
                _serialize_station(station)
                for station in Station.objects.order_by("-id_station")[:5]
            ],
            "recent_bornes": [
                _serialize_borne(borne)
                for borne in Borne.objects.select_related("station").order_by("-id_borne")[:5]
            ],
            "recent_emplacements": [
                _serialize_emplacement(emplacement)
                for emplacement in Emplacement.objects.select_related("station", "borne").order_by("-id_emplacement")[:5]
            ],
        }
    )


@_schema("Lire la supervision technique administrateur", tags=["Administration"])
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_supervision(request):
    """Return live supervision data for devices, alerts and sensors."""
    return Response(build_admin_supervision_payload())


@_schema("Lire la supervision technique du technicien connecté", tags=["Technicien"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def technician_supervision(request):
    """Return supervision data limited to the current technician station scope."""
    if request.user.is_staff:
        return Response(build_admin_supervision_payload())

    technicien = _technician_for_user(request.user)
    if technicien is None:
        return Response(
            {"detail": "Aucun profil technicien associé à ce compte."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(build_admin_supervision_payload(station_ids=_station_ids_for_technician(technicien)))


@_schema("Prendre en charge une alerte", tags=["Technicien"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def technician_acknowledge_alert(request, alert_id):
    """Mark one scoped alert as taken in charge by the current technician."""
    alert = alert_queryset().filter(id_alerte=alert_id).first()
    if alert is None:
        return Response({"detail": "Alerte introuvable."}, status=status.HTTP_404_NOT_FOUND)

    technicien, error_response = _technician_can_manage_alert(request.user, alert)
    if error_response is not None:
        return error_response

    try:
        alert = acknowledge_alert(alert, technicien)
    except AlertWorkflowError:
        return Response(
            {"detail": ALERT_WORKFLOW_ERROR_DETAIL},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"alert": serialize_alert_supervision(alert)})


@_schema("Résoudre une alerte", tags=["Technicien"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def technician_resolve_alert(request, alert_id):
    """Resolve one scoped alert after intervention or operational verification."""
    alert = alert_queryset().filter(id_alerte=alert_id).first()
    if alert is None:
        return Response({"detail": "Alerte introuvable."}, status=status.HTTP_404_NOT_FOUND)

    technicien, error_response = _technician_can_manage_alert(request.user, alert)
    if error_response is not None:
        return error_response

    note = str(request.data.get("note") or "").strip()
    try:
        alert = resolve_alert(alert, technicien, note=note)
    except AlertWorkflowError:
        return Response(
            {"detail": ALERT_WORKFLOW_ERROR_DETAIL},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"alert": serialize_alert_supervision(alert)})


@_schema("Lister les reservations administrateur", tags=["Administration"])
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_reservations(request):
    """Return upcoming and archived reservations for administrators."""
    reservations_qs = (
        Reservation.objects.select_related(
            "utilisateur",
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
            "authentification",
            "authentification__type_auth",
        )
        .order_by("-date_debut")
    )
    now = timezone.now()
    upcoming = reservations_qs.filter(date_fin__gte=now).exclude(statut="annulee")
    archived = reservations_qs.filter(date_fin__lt=now) | reservations_qs.filter(statut="annulee")
    return Response(
        {
            "upcoming": [ReservationSerializer(reservation).data for reservation in upcoming],
            "archived": [ReservationSerializer(reservation).data for reservation in archived.distinct()],
        }
    )


@_schema("Lister les sessions de recharge administrateur", tags=["Administration"])
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_sessions(request):
    """Return active and archived charging sessions for administrators."""
    sessions_qs = (
        ChargingSession.objects.select_related(
            "reservation",
            "reservation__utilisateur",
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
        )
        .order_by("-start_time")
    )
    active = sessions_qs.filter(end_time__isnull=True)
    archived = sessions_qs.filter(end_time__isnull=False)
    return Response(
        {
            "active": [_serialize_session(session) | {
                "utilisateur_pseudo": session.reservation.utilisateur.pseudo if session.reservation.utilisateur else "-",
                "reference_code": session.reservation.reference_code,
            } for session in active],
            "archived": [_serialize_session(session) | {
                "utilisateur_pseudo": session.reservation.utilisateur.pseudo if session.reservation.utilisateur else "-",
                "reference_code": session.reservation.reference_code,
            } for session in archived],
        }
    )


@_schema("Lister les utilisateurs administrateur", tags=["Administration"], operation_id="admin_users_list", methods=["GET"])
@_schema("Créer un utilisateur administrateur", request=AdminUserUpdateSerializer, tags=["Administration"], operation_id="admin_users_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_users(request):
    """List users or create a user from the administration API."""
    if request.method == "GET":
        users = User.objects.select_related("profil", "technicien_profile").order_by("-date_joined")
        return _list_response(request, users, serializer_class=AdminUserSerializer)

    payload = request.data
    required = ("pseudo", "email", "password")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return Response(
            {"detail": f"Champs manquants: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not request.user.is_superuser and any(_as_bool(payload.get(field, False)) for field in PRIVILEGED_USER_FIELDS):
        return Response(
            {"detail": "Seul un super-administrateur peut modifier les roles administrateur."},
            status=status.HTTP_403_FORBIDDEN,
        )

    is_superuser = _as_bool(payload.get("is_superuser", False))
    is_staff = _as_bool(payload.get("is_staff", False)) or is_superuser
    user_status = payload.get("statut", UserStatus.ACTIVE)
    if user_status not in UserStatus.values:
        return Response(
            {"statut": ["Statut utilisateur invalide."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if is_superuser:
        user = User.objects.create_superuser(
            pseudo=payload["pseudo"],
            email=payload["email"],
            password=payload["password"],
            statut=user_status,
            is_staff=is_staff,
        )
    else:
        user = User.objects.create_user(
            pseudo=payload["pseudo"],
            email=payload["email"],
            password=payload["password"],
            statut=user_status,
            is_staff=is_staff,
            is_superuser=False,
        )
    profile_name = payload.get("nom") or payload["pseudo"]
    ProfilUtilisateur.objects.create(
        utilisateur=user,
        nom=profile_name,
        telephone=payload.get("telephone", ""),
    )
    return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


@_schema("Lire un utilisateur", tags=["Administration"], operation_id="admin_user_retrieve", methods=["GET"])
@_schema("Modifier un utilisateur", request=AdminUserUpdateSerializer, tags=["Administration"], operation_id="admin_user_update", methods=["PATCH"])
@_schema("Supprimer un utilisateur", responses={204: None}, tags=["Administration"], operation_id="admin_user_delete", methods=["DELETE"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_user_detail(request, user_id):
    """Retrieve, update or delete one user from the administration API."""
    try:
        user = User.objects.select_related("profil", "technicien_profile").get(id_user=user_id)
    except User.DoesNotExist:
        return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(AdminUserSerializer(user).data)

    if request.method == "PATCH":
        role_error = _forbid_privileged_role_change_response(request, request.data)
        if role_error is not None:
            return role_error

        serializer = AdminUserUpdateSerializer(
            instance=user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(AdminUserSerializer(user).data)

    user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@_schema("Generer un mot de passe temporaire utilisateur", tags=["Administration"])
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_reset_user_password(request, user_id):
    """Generate and set a new temporary password for a user."""
    try:
        user = User.objects.get(id_user=user_id)
    except User.DoesNotExist:
        return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    temporary_password = _generate_temporary_password(user)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])
    _log_security_event(
        request,
        user,
        f"admin:{request.user.pseudo}:password_reset",
    )
    return Response(
        {
            "message": "Mot de passe temporaire généré.",
            "temporary_password": temporary_password,
        }
    )


@_schema("Lister ou créer les badges RFID d'un utilisateur", request=OpenApiTypes.OBJECT, tags=["Administration"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_user_auth_methods(request, user_id):
    """List active RFID badges for a user, or register a replacement badge."""
    try:
        user = User.objects.get(id_user=user_id)
    except User.DoesNotExist:
        return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        methods = (
            Authentification.objects.filter(utilisateur=user, type_auth__libelle="RFID", is_active=True)
            .exclude(display_value="")
            .select_related("type_auth")
            .order_by("-expiration", "-created_at", "-id_auth")
        )
        return _list_response(request, methods, serializer_func=_serialize_admin_auth_method)

    auth_value = (request.data.get("auth_value") or request.data.get("value") or "").strip()
    try:
        auth_method = _ensure_rfid_auth(user, auth_value)
    except RfidCredentialConflict:
        return Response({"auth_value": "Ce badge RFID est déjà associé à un autre compte."}, status=status.HTTP_409_CONFLICT)
    except ValueError:
        return Response({"auth_value": "Badge RFID invalide."}, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    Authentification.objects.filter(
        utilisateur=user,
        type_auth__libelle="RFID",
        is_active=True,
    ).exclude(id_auth=auth_method.id_auth).update(
        is_active=False,
        expiration=now,
        metadata={
            "revoked_at": now.isoformat(),
            "revoked_by": str(request.user.id_user),
            "revocation_source": "admin_replacement",
        },
    )
    _log_security_event(
        request,
        user,
        f"admin:{request.user.pseudo}:rfid_registered:{auth_method.id_auth}",
    )
    return Response(
        {
            "message": "Badge RFID enregistre.",
            "auth_method": _serialize_admin_auth_method(auth_method),
        },
        status=status.HTTP_201_CREATED,
    )


@_schema("Révoquer un badge RFID utilisateur", responses={204: None}, tags=["Administration"])
@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_revoke_user_auth_method(request, user_id, auth_id):
    """Soft-revoke an active RFID badge from the administration API."""
    try:
        user = User.objects.get(id_user=user_id)
    except User.DoesNotExist:
        return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    auth_method = (
        Authentification.objects.filter(
            id_auth=auth_id,
            utilisateur=user,
            type_auth__libelle="RFID",
            is_active=True,
        )
        .select_related("type_auth")
        .first()
    )
    if auth_method is None:
        return Response({"detail": "Badge RFID introuvable."}, status=status.HTTP_404_NOT_FOUND)

    auth_method.is_active = False
    auth_method.expiration = timezone.now()
    auth_method.metadata = {
        **(auth_method.metadata or {}),
        "revoked_at": timezone.now().isoformat(),
        "revoked_by": str(request.user.id_user),
        "revocation_source": "admin",
    }
    auth_method.save(update_fields=["is_active", "expiration", "metadata"])
    _log_security_event(
        request,
        user,
        f"admin:{request.user.pseudo}:rfid_revoked:{auth_method.id_auth}",
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@_schema("Lister les stations", tags=["Administration"], operation_id="admin_stations_list", methods=["GET"])
@_schema("Créer une station", request=StationSerializer, tags=["Administration"], operation_id="admin_station_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_stations(request):
    """List stations or create a station from the administration API."""
    if request.method == "GET":
        stations = Station.objects.order_by("nom")
        return _list_response(request, stations, serializer_class=StationSerializer)

    serializer = StationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    station = serializer.save()
    _clear_station_catalog_cache()
    return Response(StationSerializer(station).data, status=status.HTTP_201_CREATED)


@_schema("Lire une station", tags=["Administration"], operation_id="admin_station_retrieve", methods=["GET"])
@_schema("Modifier une station", request=StationSerializer, tags=["Administration"], operation_id="admin_station_update", methods=["PATCH"])
@_schema("Supprimer une station", responses={204: None}, tags=["Administration"], operation_id="admin_station_delete", methods=["DELETE"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_station_detail(request, station_id):
    """Retrieve, update or delete one station from the administration API."""
    try:
        station = Station.objects.get(id_station=station_id)
    except Station.DoesNotExist:
        return Response({"detail": "Station introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(StationSerializer(station).data)

    if request.method == "PATCH":
        serializer = StationSerializer(instance=station, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _clear_station_catalog_cache()
        return Response(StationSerializer(station).data)

    _clear_station_catalog_cache()
    station.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@_schema("Lister les bornes", tags=["Administration"], operation_id="admin_bornes_list", methods=["GET"])
@_schema("Créer une borne", request=BorneSerializer, tags=["Administration"], operation_id="admin_borne_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_bornes(request):
    """List physical charging cabinets or create one from the administration API."""
    if request.method == "GET":
        bornes = Borne.objects.select_related("station").prefetch_related("emplacements").order_by("station__nom", "numero")
        return _list_response(request, bornes, serializer_class=BorneSerializer)

    serializer = BorneSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    borne = serializer.save()
    _clear_station_catalog_cache()
    return Response(BorneSerializer(borne).data, status=status.HTTP_201_CREATED)


@_schema("Lire une borne", tags=["Administration"], operation_id="admin_borne_retrieve", methods=["GET"])
@_schema("Modifier une borne", request=BorneSerializer, tags=["Administration"], operation_id="admin_borne_update", methods=["PATCH"])
@_schema("Supprimer une borne", responses={204: None}, tags=["Administration"], operation_id="admin_borne_delete", methods=["DELETE"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_borne_detail(request, borne_id):
    """Retrieve, update or delete one physical charging cabinet."""
    try:
        borne = Borne.objects.select_related("station").prefetch_related("emplacements").get(id_borne=borne_id)
    except Borne.DoesNotExist:
        return Response({"detail": "Borne introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(BorneSerializer(borne).data)

    if request.method == "PATCH":
        serializer = BorneSerializer(instance=borne, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _clear_station_catalog_cache()
        return Response(BorneSerializer(borne).data)

    _clear_station_catalog_cache()
    borne.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@_schema("Lister les emplacements", tags=["Administration"], operation_id="admin_emplacements_list", methods=["GET"])
@_schema("Créer un emplacement", request=EmplacementSerializer, tags=["Administration"], operation_id="admin_emplacement_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_emplacements(request):
    """List charging bays or create one from the administration API."""
    if request.method == "GET":
        emplacements = Emplacement.objects.select_related("station", "borne").order_by("station__nom", "borne__numero", "numero")
        return _list_response(request, emplacements, serializer_class=EmplacementSerializer)

    serializer = EmplacementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    emplacement = serializer.save()
    _clear_station_catalog_cache()
    return Response(EmplacementSerializer(emplacement).data, status=status.HTTP_201_CREATED)


@_schema("Lire un emplacement", tags=["Administration"], operation_id="admin_emplacement_retrieve", methods=["GET"])
@_schema("Modifier un emplacement", request=EmplacementSerializer, tags=["Administration"], operation_id="admin_emplacement_update", methods=["PATCH"])
@_schema("Supprimer un emplacement", responses={204: None}, tags=["Administration"], operation_id="admin_emplacement_delete", methods=["DELETE"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_emplacement_detail(request, emplacement_id):
    """Retrieve, update or delete one charging bay from the admin API."""
    try:
        emplacement = Emplacement.objects.select_related("station", "borne").get(id_emplacement=emplacement_id)
    except Emplacement.DoesNotExist:
        return Response({"detail": "Emplacement introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(EmplacementSerializer(emplacement).data)

    if request.method == "PATCH":
        serializer = EmplacementSerializer(instance=emplacement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _clear_station_catalog_cache()
        return Response(EmplacementSerializer(emplacement).data)

    _clear_station_catalog_cache()
    emplacement.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


def _device_queryset():
    """Return ESP32 devices with their physical location loaded."""
    return Device.objects.select_related(
        "emplacement",
        "emplacement__station",
        "emplacement__borne",
    ).order_by(
        "emplacement__station__nom",
        "emplacement__borne__numero",
        "emplacement__numero",
    )


@_schema("Lister les ESP32", tags=["Administration"], operation_id="admin_devices_list")
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_devices(request):
    """List embedded devices with inventory and firmware policy fields."""
    return _list_response(
        request,
        _device_queryset(),
        serializer_class=DeviceAdminSerializer,
    )


@_schema("Lire un ESP32", tags=["Administration"], operation_id="admin_device_retrieve", methods=["GET"])
@_schema("Modifier la politique firmware d'un ESP32", request=DeviceAdminSerializer, tags=["Administration"], operation_id="admin_device_update", methods=["PATCH"])
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_device_detail(request, device_id):
    """Retrieve or update one ESP32 inventory record."""
    try:
        device = _device_queryset().get(id_device=device_id)
    except Device.DoesNotExist:
        return Response({"detail": "ESP32 introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(DeviceAdminSerializer(device).data)

    serializer = DeviceAdminSerializer(instance=device, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    device = serializer.save()
    update_fields = []
    update_firmware_compliance_status(device, update_fields=update_fields)
    if update_fields:
        device.save(update_fields=list(dict.fromkeys(update_fields)))
    return Response(DeviceAdminSerializer(device).data)


@_schema("Planifier une mise a jour OTA ESP32", request=OpenApiTypes.OBJECT, tags=["Administration"])
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_device_schedule_ota(request, device_id):
    """Record an admin-approved firmware update target for one ESP32."""
    try:
        device = _device_queryset().get(id_device=device_id)
    except Device.DoesNotExist:
        return Response({"detail": "ESP32 introuvable."}, status=status.HTTP_404_NOT_FOUND)

    try:
        schedule_ota_update(
            device,
            target_version=request.data.get("target_version"),
            update_url=request.data.get("update_url", ""),
        )
    except ValueError:
        return Response({"target_version": "La version cible du firmware est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

    device = _device_queryset().get(id_device=device_id)
    return Response(DeviceAdminSerializer(device).data)


@_schema("Lister les moyens d'authentification", tags=["Compte"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auth_methods(request):
    """List saved RFID authentication methods for the authenticated user."""
    if request.method == "GET":
        methods = (
            Authentification.objects.filter(utilisateur=request.user, type_auth__libelle="RFID", is_active=True)
            .exclude(display_value="")
            .select_related("type_auth")
            .order_by("-expiration", "-id_auth")
        )
        return _list_response(request, methods, serializer_func=_serialize_auth_method)

    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@_schema("Créer un moyen d'authentification", request=OpenApiTypes.OBJECT, tags=["Compte"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthFactorRateThrottle])
def create_auth_method(request):
    """Create or refresh a saved RFID authentication method for the user."""
    auth_mode = (request.data.get("auth_mode") or request.data.get("type") or "").strip().lower()
    auth_value = (request.data.get("auth_value") or request.data.get("value") or "").strip()

    if auth_mode != "rfid":
        return Response(
            {"detail": "Seul RFID peut être créé manuellement depuis le profil."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        auth_method = _ensure_rfid_auth(request.user, auth_value)
    except RfidCredentialConflict:
        return Response({"auth_value": "Ce badge RFID est déjà associé à un autre compte."}, status=status.HTTP_409_CONFLICT)
    except ValueError:
        return Response({"auth_value": "Badge RFID invalide."}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "message": "Moyen d'authentification enregistre.",
            "auth_method": _serialize_auth_method(auth_method),
            "clear_value": auth_value,
        },
        status=status.HTTP_201_CREATED,
    )


@_schema("Generer un code d'association RFID", responses=OpenApiTypes.OBJECT, tags=["Compte"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthFactorRateThrottle])
def create_rfid_link_code(request):
    """Create a short one-use code used to link a physical RFID badge on a kiosk."""
    code = _generate_rfid_link_code()
    expires_at = timezone.now() + timedelta(seconds=RFID_LINK_CODE_TTL_SECONDS)
    cache.set(
        _rfid_link_cache_key(code),
        {
            "user_id": str(request.user.id_user),
            "pseudo": request.user.pseudo,
            "created_at": timezone.now().isoformat(),
            "expires_at": expires_at.isoformat(),
        },
        timeout=RFID_LINK_CODE_TTL_SECONDS,
    )
    _log_security_event(request, request.user, f"user:{request.user.pseudo}:rfid_link_code_created")
    return Response(
        {
            "code": code,
            "expires_at": expires_at.isoformat(),
            "expires_in": RFID_LINK_CODE_TTL_SECONDS,
        },
        status=status.HTTP_201_CREATED,
    )


@_schema("Supprimer un moyen d'authentification", responses={204: None}, tags=["Compte"])
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_auth_method(request, auth_id):
    """Delete a saved RFID authentication method owned by the user."""
    auth_method = Authentification.objects.filter(
        id_auth=auth_id,
        utilisateur=request.user,
        type_auth__libelle="RFID",
        is_active=True,
    ).first()

    if auth_method is None:
        return Response({"detail": "Badge RFID introuvable."}, status=status.HTTP_404_NOT_FOUND)

    auth_method.is_active = False
    auth_method.expiration = timezone.now()
    auth_method.metadata = {
        **(auth_method.metadata or {}),
        "revoked_at": timezone.now().isoformat(),
        "revocation_source": "self_service",
    }
    auth_method.save(update_fields=["is_active", "expiration", "metadata"])
    _log_security_event(request, request.user, f"user:{request.user.pseudo}:rfid_revoked:{auth_method.id_auth}")
    return Response(status=status.HTTP_204_NO_CONTENT)


@_schema("Lister l'historique d'authentification", tags=["Compte"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auth_history(request):
    """Return the reservation authentication history for the user."""
    reservations_qs = (
        Reservation.objects.filter(utilisateur=request.user)
        .select_related(
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
            "authentification",
            "authentification__type_auth",
        )
        .order_by("-date_debut")
    )

    history = []
    for reservation in reservations_qs:
        auth_method = reservation.authentification
        history.append(
            {
                "id_reservation": str(reservation.id_reservation),
                "reference_code": reservation.reference_code,
                "station_nom": reservation.emplacement.station.nom,
                "borne_nom": reservation.emplacement.borne.nom,
                "borne_numero": reservation.emplacement.borne.numero,
                "emplacement": reservation.emplacement.numero,
                "auth_mode": reservation.auth_choice,
                "auth_type": auth_method.type_auth.libelle if auth_method and auth_method.type_auth else reservation.auth_choice.upper(),
                "auth_value": auth_method.display_value if auth_method else "",
                "auth_expiration": auth_method.expiration.isoformat() if auth_method else None,
                "auth_source": "generated" if reservation.auth_choice in {"qr", "code"} else "saved",
                "date_debut": reservation.date_debut.isoformat(),
                "date_fin": reservation.date_fin.isoformat(),
                "statut": reservation.statut,
            }
        )

    return _list_response(request, history, serializer_func=lambda item: item)


@_schema(
    "Lister les emplacements disponibles pour une réservation",
    parameters=[
        OpenApiParameter("station", OpenApiTypes.UUID, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("date_debut", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("date_fin", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=True),
    ],
    tags=["Réservations"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def reservation_availability(request):
    """List charging bays available for one station and time slot."""
    station_id = request.query_params.get("station")
    date_debut = request.query_params.get("date_debut")
    date_fin = request.query_params.get("date_fin")

    if not station_id:
        return Response({"detail": "Le paramètre station est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

    if not date_debut or not date_fin:
        return Response({"detail": "Les dates sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        date_debut_dt = datetime.fromisoformat(date_debut.replace("Z", "+00:00"))
        date_fin_dt = datetime.fromisoformat(date_fin.replace("Z", "+00:00"))
    except ValueError:
        return Response({"detail": "Format de date invalide."}, status=status.HTTP_400_BAD_REQUEST)

    if not _round_to_thirty_minutes(date_debut_dt) or not _round_to_thirty_minutes(date_fin_dt):
        return Response(
            {"detail": "Les horaires doivent être alignés sur des tranches de 30 minutes."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if date_debut_dt < timezone.now():
        return Response(
            {"detail": "La réservation doit commencer dans le futur."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _duration_is_valid(date_debut_dt, date_fin_dt):
        return Response(
            {"detail": reservation_duration_error_message()},
            status=status.HTTP_400_BAD_REQUEST,
        )

    station = Station.objects.filter(id_station=station_id).first()
    if not station:
        return Response({"detail": "Station introuvable."}, status=status.HTTP_404_NOT_FOUND)

    available_emplacements = _available_emplacements(station, date_debut_dt, date_fin_dt)

    return Response(
        {
            "station": _serialize_station(station),
            "available_count": len(available_emplacements),
            "total_count": station.emplacements.count(),
            "available": bool(available_emplacements),
            "duration_minutes": reservation_duration_minutes(date_debut_dt, date_fin_dt),
            "allowed_durations_minutes": list(RESERVATION_DURATION_MINUTES),
            "available_emplacements": [
                _serialize_emplacement(emplacement)
                for emplacement in available_emplacements
            ],
        }
    )


@_schema("Lister le catalogue des stations", tags=["Stations"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stations_catalog(request):
    """Return stations with their charging bays for reservation screens."""
    payload = cache.get(STATIONS_CATALOG_CACHE_KEY)
    if payload is None:
        stations = (
            Station.objects.prefetch_related(
                Prefetch(
                    "bornes",
                    queryset=Borne.objects.prefetch_related("emplacements").order_by("numero"),
                ),
                Prefetch(
                    "emplacements",
                    queryset=Emplacement.objects.select_related("station", "borne").order_by("borne__numero", "numero"),
                )
            )
            .order_by("nom")
        )
        payload = {
            "results": [
                {
                    **_serialize_station(station),
                    "bornes": [
                        _serialize_borne(borne)
                        for borne in station.bornes.all()
                    ],
                    "emplacements": [
                        _serialize_emplacement(emplacement)
                        for emplacement in station.emplacements.all()
                    ],
                }
                for station in stations
            ]
        }
        cache.set(
            STATIONS_CATALOG_CACHE_KEY,
            payload,
            timeout=settings.STATIONS_CATALOG_CACHE_SECONDS,
        )
    return Response(payload)


@_schema("Lister ou créer des réservations", request=ReservationCreateSerializer, tags=["Réservations"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def reservations(request):
    """List user reservations or create a new reservation with access data."""
    if request.method == "GET":
        queryset = (
            Reservation.objects.filter(utilisateur=request.user)
            .select_related("emplacement", "emplacement__station", "emplacement__borne", "authentification", "authentification__type_auth")
            .order_by("-date_debut")
        )
        return _list_response(request, queryset, serializer_class=ReservationSerializer)

    serializer = ReservationCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if not _round_to_thirty_minutes(data["date_debut"]) or not _round_to_thirty_minutes(data["date_fin"]):
        return Response(
            {"detail": "Les horaires doivent être alignés sur des tranches de 30 minutes."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if data["date_debut"] < timezone.now():
        return Response(
            {"detail": "La réservation doit commencer dans le futur."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _duration_is_valid(data["date_debut"], data["date_fin"]):
        return Response(
            {"detail": reservation_duration_error_message()},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        station = Station.objects.select_for_update().filter(id_station=data["station"]).first()
        if not station:
            return Response({"detail": "Station introuvable."}, status=status.HTTP_404_NOT_FOUND)

        requested_emplacement_id = data.get("emplacement")
        if requested_emplacement_id:
            emplacement = Emplacement.objects.select_related("station").filter(
                id_emplacement=requested_emplacement_id,
                station=station,
            ).first()
            if not emplacement:
                return Response(
                    {"detail": "L'emplacement ne correspond pas a la station choisie."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if _reservation_overlaps(emplacement, data["date_debut"], data["date_fin"]):
                return Response(
                    {"detail": "Cet emplacement n'est pas disponible sur cette plage horaire."},
                    status=status.HTTP_409_CONFLICT,
                )
        else:
            available_emplacements = _available_emplacements(station, data["date_debut"], data["date_fin"])
            if not available_emplacements:
                return Response(
                    {"detail": "Aucun emplacement disponible dans cette station sur ce créneau."},
                    status=status.HTTP_409_CONFLICT,
                )
            emplacement = available_emplacements[0]

        auth_mode = data["auth_mode"].lower()
        auth_method = None
        clear_value = None
        reservation_code = _generate_reservation_code()
        if auth_mode == "rfid":
            auth_method = _get_saved_rfid_auth(request.user)
            if auth_method is None:
                return Response(
                    {"auth_value": "Ajoute d'abord un badge RFID dans ton profil."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif auth_mode == "code" and not _user_phone_number(request.user):
            return Response(
                {"telephone": "Un numéro de téléphone est obligatoire pour recevoir un code SMS."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif (
            auth_mode == "code"
            and getattr(settings, "SMS_REQUIRE_VERIFIED_PHONE", False)
            and not _user_phone_is_verified(request.user)
        ):
            return Response(
                {"telephone": "Le numéro de téléphone doit être vérifié pour choisir le mode code SMS."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            auth_method, clear_value = _create_temporary_auth(
                request.user,
                auth_mode,
                data["date_fin"],
                reservation_code,
            )

        reservation = Reservation.objects.create(
            utilisateur=request.user,
            emplacement=emplacement,
            reference_code=reservation_code,
            authentification=auth_method,
            auth_choice=auth_mode,
            date_debut=data["date_debut"],
            date_fin=data["date_fin"],
            statut="confirmee",
        )

        response = {
            "message": "Réservation créée.",
            "reservation": ReservationSerializer(reservation).data,
        }
        if clear_value:
            access_payload = _build_access_payload(
                auth_mode,
                clear_value,
                auth_method,
                data["date_fin"],
            )
            response["access_payload"] = access_payload
            if auth_mode == "qr":
                _schedule_reservation_qr_email(request, reservation, auth_method, access_payload)
        response["reservation_code"] = reservation.reference_code
        return Response(response, status=status.HTTP_201_CREATED)


@_schema("Annuler une réservation", tags=["Réservations"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_reservation(request, reservation_id):
    """Cancel one reservation owned by the authenticated user."""
    try:
        reservation = Reservation.objects.select_related("utilisateur", "emplacement", "emplacement__station", "emplacement__borne").get(
            id_reservation=reservation_id,
            utilisateur=request.user,
        )
    except Reservation.DoesNotExist:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if not _cancel_reservation(reservation):
        return Response(
            {"detail": "Cette réservation ne peut plus être annulée."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(ReservationSerializer(reservation).data)


@_schema("Afficher l'accès temporaire d'une réservation", tags=["Réservations"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reservation_access_payload(request, reservation_id):
    """Return the current temporary QR or code access for an active reservation."""
    try:
        reservation = Reservation.objects.select_related(
            "utilisateur",
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
            "authentification",
            "authentification__type_auth",
        ).get(
            id_reservation=reservation_id,
            utilisateur=request.user,
        )
    except Reservation.DoesNotExist:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if reservation.auth_choice not in {"qr", "code"}:
        return Response(
            {"detail": "Cette réservation utilise un badge RFID."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if reservation.statut in {"annulee", "terminee"} or reservation.date_fin < timezone.now():
        return Response(
            {"detail": "L'accès temporaire ne peut plus être régénéré pour cette réservation."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    auth_method, access_value = _get_temporary_access_value(reservation)
    if auth_method is None or access_value is None:
        return Response(
            {"detail": "L'accès temporaire ne peut pas être affiché. Régénérez-le depuis l'administration."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "reservation_code": reservation.reference_code,
            "access_payload": _build_access_payload(
                reservation.auth_choice,
                access_value,
                auth_method,
                reservation.date_fin,
            ),
        }
    )


@_schema("Envoyer le code SMS d'une réservation", tags=["Réservations"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SmsRateThrottle])
def send_reservation_access_code(request, reservation_id):
    """Send the current temporary reservation code by SMS."""
    try:
        reservation = Reservation.objects.select_related(
            "utilisateur",
            "utilisateur__profil",
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
            "authentification",
            "authentification__type_auth",
        ).get(
            id_reservation=reservation_id,
            utilisateur=request.user,
        )
    except Reservation.DoesNotExist:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if reservation.auth_choice != "code":
        return Response(
            {"detail": "Cette réservation n'utilise pas de code SMS."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if reservation.statut in {"annulee", "terminee"} or reservation.date_fin < timezone.now():
        return Response(
            {"detail": "Le code SMS ne peut plus être envoyé pour cette réservation."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    auth_method, access_value = _get_temporary_access_value(reservation)
    if auth_method is None or access_value is None:
        return Response(
            {"detail": "Le code SMS ne peut pas être envoyé. Régénérez l'accès depuis l'administration."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    delivery, error_response = _send_reservation_sms_code(request, reservation, auth_method, access_value)
    if error_response is not None:
        return error_response

    return Response(
        {
            "reservation_code": reservation.reference_code,
            "message": "Code SMS envoyé.",
            "sms": {
                "sent_at": delivery["sent_at"].isoformat(),
                "recipient_hint": delivery["recipient_hint"],
                "backend": delivery["backend"],
            },
            "access_payload": _build_access_payload(
                reservation.auth_choice,
                access_value,
                auth_method,
                reservation.date_fin,
            ),
        }
    )


@_schema("Annuler une réservation en administration", tags=["Administration"])
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_cancel_reservation(request, reservation_id):
    """Cancel any cancellable reservation from the administration API."""
    try:
        reservation = Reservation.objects.select_related("utilisateur", "emplacement", "emplacement__station", "emplacement__borne").get(
            id_reservation=reservation_id,
        )
    except Reservation.DoesNotExist:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if not _cancel_reservation(reservation):
        return Response(
            {"detail": "Cette réservation ne peut plus être annulée."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(ReservationSerializer(reservation).data)


@_schema("Régénérer l'accès temporaire d'une réservation en administration", tags=["Administration"])
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_reservation_access_payload(request, reservation_id):
    """Regenerate a temporary QR or code credential from the administration API."""
    try:
        reservation = Reservation.objects.select_related(
            "utilisateur",
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
            "authentification",
            "authentification__type_auth",
        ).get(id_reservation=reservation_id)
    except Reservation.DoesNotExist:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if not _temporary_access_can_be_rotated(reservation):
        return Response(
            {"detail": "L'accès temporaire ne peut pas être régénéré pour cette réservation."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    _refresh_temporary_auth(reservation)
    if reservation.utilisateur:
        _log_security_event(
            request,
            reservation.utilisateur,
            f"admin:{request.user.pseudo}:temporary_access_regenerated:{reservation.reference_code}",
        )
    return Response(
        {
            "reservation": ReservationSerializer(reservation).data,
            "message": "Accès temporaire régénéré.",
        }
    )


@_schema("Révoquer l'accès temporaire d'une réservation en administration", tags=["Administration"])
@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_revoke_reservation_access(request, reservation_id):
    """Revoke the temporary credential attached to a QR/code reservation."""
    try:
        reservation = Reservation.objects.select_related(
            "utilisateur",
            "emplacement",
            "emplacement__station",
            "emplacement__borne",
            "authentification",
            "authentification__type_auth",
        ).get(id_reservation=reservation_id)
    except Reservation.DoesNotExist:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if reservation.auth_choice not in {"qr", "code"}:
        return Response(
            {"detail": "Cette réservation utilise un badge RFID."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if reservation.authentification is None or not reservation.authentification.is_active:
        return Response({"detail": "Aucun accès temporaire actif."}, status=status.HTTP_404_NOT_FOUND)

    auth_method = reservation.authentification
    auth_method.is_active = False
    auth_method.expiration = timezone.now()
    auth_method.metadata = {
        **(auth_method.metadata or {}),
        "revoked_at": timezone.now().isoformat(),
        "revoked_by": str(request.user.id_user),
        "revocation_source": "admin",
    }
    auth_method.save(update_fields=["is_active", "expiration", "metadata"])
    if reservation.utilisateur:
        _log_security_event(
            request,
            reservation.utilisateur,
            f"admin:{request.user.pseudo}:temporary_access_revoked:{reservation.reference_code}",
        )
    return Response(ReservationSerializer(reservation).data)


@_schema("Lister les maintenances du technicien connecté", tags=["Technicien"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def technician_maintenances(request):
    """List maintenance interventions assigned to the current technician."""
    technicien = _technician_for_user(request.user)
    if technicien is None and not request.user.is_staff:
        return Response(
            {"detail": "Aucun profil technicien associé à ce compte."},
            status=status.HTTP_404_NOT_FOUND,
        )

    maintenances = Maintenance.objects.select_related("station", "technicien").prefetch_related("station__emplacements")
    if technicien is not None:
        maintenances = maintenances.filter(technicien=technicien)
    maintenances = maintenances.order_by("date_planifiee")
    return _list_response(request, maintenances, serializer_class=TechnicianMaintenanceSerializer)


@_schema("Lister les techniciens", tags=["Administration"], operation_id="admin_technicians_list", methods=["GET"])
@_schema("Créer un technicien", request=TechnicianSerializer, tags=["Administration"], operation_id="admin_technician_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_technicians(request):
    """List technicians or create a technician from the administration API."""
    if request.method == "GET":
        technicians = (
            Technicien.objects.select_related("utilisateur")
            .prefetch_related(_active_station_assignments_prefetch())
            .order_by("nom")
        )
        return _list_response(request, technicians, serializer_class=TechnicianSerializer)

    serializer = TechnicianSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    station_scope = serializer.validated_data.get("station_scope")

    utilisateur = None
    utilisateur_id = serializer.validated_data.get("utilisateur")
    if utilisateur_id:
        utilisateur = utilisateur_id

    with transaction.atomic():
        technician = Technicien.objects.create(
            utilisateur=utilisateur,
            nom=serializer.validated_data["nom"],
            email=serializer.validated_data["email"],
            telephone=serializer.validated_data.get("telephone", ""),
        )
        _sync_technician_station_scope(technician, station_scope)

    technician = (
        Technicien.objects.select_related("utilisateur")
        .prefetch_related(_active_station_assignments_prefetch())
        .get(id_technicien=technician.id_technicien)
    )
    return Response(TechnicianSerializer(technician).data, status=status.HTTP_201_CREATED)


@_schema("Lire un technicien", tags=["Administration"], operation_id="admin_technician_retrieve", methods=["GET"])
@_schema("Modifier un technicien", request=TechnicianSerializer, tags=["Administration"], operation_id="admin_technician_update", methods=["PATCH"])
@_schema("Supprimer un technicien", responses={204: None}, tags=["Administration"], operation_id="admin_technician_delete", methods=["DELETE"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_technician_detail(request, technician_id):
    """Retrieve, update or delete one technician from the admin API."""
    try:
        technician = (
            Technicien.objects.select_related("utilisateur")
            .prefetch_related(_active_station_assignments_prefetch())
            .get(id_technicien=technician_id)
        )
    except Technicien.DoesNotExist:
        return Response({"detail": "Technicien introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(TechnicianSerializer(technician).data)

    if request.method == "DELETE":
        technician.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = TechnicianSerializer(instance=technician, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    station_scope = serializer.validated_data.get("station_scope")

    with transaction.atomic():
        technician.nom = serializer.validated_data.get("nom", technician.nom)
        technician.email = serializer.validated_data.get("email", technician.email)
        technician.telephone = serializer.validated_data.get("telephone", technician.telephone)
        if "utilisateur" in serializer.validated_data:
            technician.utilisateur = serializer.validated_data["utilisateur"]
        technician.save()
        _sync_technician_station_scope(technician, station_scope)

    technician = (
        Technicien.objects.select_related("utilisateur")
        .prefetch_related(_active_station_assignments_prefetch())
        .get(id_technicien=technician.id_technicien)
    )
    return Response(TechnicianSerializer(technician).data)


@_schema(
    "Lister les affectations technicien-station",
    tags=["Administration"],
    operation_id="admin_technician_station_assignments_list",
    methods=["GET"],
)
@_schema(
    "Affecter une station a un technicien",
    request=TechnicianStationAssignmentSerializer,
    tags=["Administration"],
    operation_id="admin_technician_station_assignment_create",
    methods=["POST"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_technician_station_assignments(request):
    """List or create station assignments for technician least privilege."""
    if request.method == "GET":
        assignments = TechnicienStation.objects.select_related("technicien", "station").order_by(
            "technicien__nom",
            "station__nom",
        )
        technician_id = request.query_params.get("technicien")
        station_id = request.query_params.get("station")
        if technician_id:
            assignments = assignments.filter(technicien_id=technician_id)
        if station_id:
            assignments = assignments.filter(station_id=station_id)
        return _list_response(request, assignments, serializer_class=TechnicianStationAssignmentSerializer)

    serializer = TechnicianStationAssignmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    assignment = serializer.save()
    assignment = TechnicienStation.objects.select_related("technicien", "station").get(
        id_assignment=assignment.id_assignment
    )
    return Response(TechnicianStationAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


@_schema(
    "Lire une affectation technicien-station",
    tags=["Administration"],
    operation_id="admin_technician_station_assignment_retrieve",
    methods=["GET"],
)
@_schema(
    "Modifier une affectation technicien-station",
    request=TechnicianStationAssignmentSerializer,
    tags=["Administration"],
    operation_id="admin_technician_station_assignment_update",
    methods=["PATCH"],
)
@_schema(
    "Supprimer une affectation technicien-station",
    responses={204: None},
    tags=["Administration"],
    operation_id="admin_technician_station_assignment_delete",
    methods=["DELETE"],
)
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_technician_station_assignment_detail(request, assignment_id):
    """Retrieve, update or delete one technician station assignment."""
    try:
        assignment = TechnicienStation.objects.select_related("technicien", "station").get(
            id_assignment=assignment_id
        )
    except TechnicienStation.DoesNotExist:
        return Response({"detail": "Affectation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(TechnicianStationAssignmentSerializer(assignment).data)

    if request.method == "DELETE":
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = TechnicianStationAssignmentSerializer(
        instance=assignment,
        data=request.data,
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    assignment = serializer.save()
    return Response(TechnicianStationAssignmentSerializer(assignment).data)


@_schema("Lister les maintenances", tags=["Administration"], operation_id="admin_maintenances_list", methods=["GET"])
@_schema("Créer une maintenance", request=MaintenanceAdminSerializer, tags=["Administration"], operation_id="admin_maintenance_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_maintenances(request):
    """List maintenance records or create one from the admin API."""
    if request.method == "GET":
        maintenances = Maintenance.objects.select_related("station", "technicien").order_by("-date_planifiee")
        return _list_response(request, maintenances, serializer_class=MaintenanceAdminSerializer)

    serializer = MaintenanceAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    maintenance = serializer.save()
    return Response(MaintenanceAdminSerializer(maintenance).data, status=status.HTTP_201_CREATED)


@_schema("Lire une maintenance", tags=["Administration"], operation_id="admin_maintenance_retrieve", methods=["GET"])
@_schema("Modifier une maintenance", request=MaintenanceAdminSerializer, tags=["Administration"], operation_id="admin_maintenance_update", methods=["PATCH"])
@_schema("Supprimer une maintenance", responses={204: None}, tags=["Administration"], operation_id="admin_maintenance_delete", methods=["DELETE"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_maintenance_detail(request, maintenance_id):
    """Retrieve, update or delete one maintenance record from the admin API."""
    try:
        maintenance = Maintenance.objects.select_related("station", "technicien").get(id_maintenance=maintenance_id)
    except Maintenance.DoesNotExist:
        return Response({"detail": "Maintenance introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(MaintenanceAdminSerializer(maintenance).data)

    if request.method == "DELETE":
        maintenance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = MaintenanceAdminSerializer(instance=maintenance, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    maintenance.refresh_from_db()
    return Response(MaintenanceAdminSerializer(maintenance).data)


@_schema("Associer un badge RFID depuis le terminal", request=OpenApiTypes.OBJECT, tags=["Terminal"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_link_rfid(request):
    """Consume a short web-generated code and link the scanned RFID UID to that user."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    link_code = (request.data.get("link_code") or request.data.get("code") or "").strip().upper()
    uid = (request.data.get("uid") or request.data.get("auth_value") or "").strip()

    if not link_code or not uid:
        return Response(
            {"detail": "link_code et uid sont obligatoires."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payload = cache.get(_rfid_link_cache_key(link_code))
    if payload is None:
        return Response(
            {"detail": "Code d'association invalide ou expire."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user = User.objects.filter(id_user=payload.get("user_id"), is_active=True).first()
    if user is None:
        cache.delete(_rfid_link_cache_key(link_code))
        return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    type_auth = _get_type_auth("RFID")
    uid_hash = _hash_secret(uid)
    existing = (
        Authentification.objects.select_related("utilisateur")
        .filter(type_auth=type_auth, hash_valeur=uid_hash, is_active=True)
        .first()
    )
    if existing is not None and existing.utilisateur_id != user.id_user:
        return Response(
            {"detail": "Ce badge RFID est déjà associé à un autre compte."},
            status=status.HTTP_409_CONFLICT,
        )

    try:
        auth_method = _ensure_rfid_auth(user, uid)
    except RfidCredentialConflict:
        return Response({"detail": "Ce badge RFID est déjà associé à un autre compte."}, status=status.HTTP_409_CONFLICT)
    now = timezone.now()
    Authentification.objects.filter(
        utilisateur=user,
        type_auth=type_auth,
        is_active=True,
    ).exclude(id_auth=auth_method.id_auth).update(
        is_active=False,
        expiration=now,
        metadata={
            "revoked_at": now.isoformat(),
            "revocation_source": "rfid_link_replacement",
        },
    )

    cache.delete(_rfid_link_cache_key(link_code))
    JournalSecurite.objects.create(
        utilisateur=user,
        action=f"user:{user.pseudo}:rfid_linked:{auth_method.id_auth}",
        ip=_client_ip(request),
        statut="success",
    )
    return Response(
        {
            "message": "Badge RFID associé.",
            "auth_method": _serialize_auth_method(auth_method),
            "user": {
                "id": str(user.id_user),
                "pseudo": user.pseudo,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@_schema("Créer une session mobile de borne", request=OpenApiTypes.OBJECT, tags=["Terminal"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_create_mobile_session(request):
    """Create a short-lived pairing session opened by a phone from the kiosk QR."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    station_id = (request.data.get("station_id") or "").strip()
    borne_id = (request.data.get("borne_id") or "").strip()
    station = None
    borne = None
    if borne_id:
        borne = Borne.objects.select_related("station").filter(id_borne=borne_id).first()
        if borne is None:
            return Response({"detail": "Borne introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if station_id and str(borne.station_id) != station_id:
            return Response(
                {"detail": "Cette borne est associée à une autre station."},
                status=status.HTTP_409_CONFLICT,
            )
        station = borne.station
    if station_id:
        station = station or Station.objects.filter(id_station=station_id).first()
        if station is None:
            return Response({"detail": "Station introuvable."}, status=status.HTTP_404_NOT_FOUND)

    token = _generate_mobile_session_token()
    now = timezone.now()
    expires_at = now + timedelta(seconds=MOBILE_SESSION_TTL_SECONDS)
    payload = {
        "token": token,
        "status": "pending",
        "station_id": str(station.id_station) if station else None,
        "station_nom": station.nom if station else "",
        "borne_id": str(borne.id_borne) if borne else None,
        "borne_nom": borne.nom if borne else "",
        "borne_numero": borne.numero if borne else None,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    _store_mobile_session(payload)

    session_url = _mobile_session_url(token, request.data.get("frontend_origin"))
    return Response(
        {
            "mobile_session": _serialize_mobile_session(payload),
            "url": session_url,
            "qr_payload": session_url,
            "qr_svg": _build_qr_svg(session_url),
        },
        status=status.HTTP_201_CREATED,
    )


@_schema("Lire une session mobile de borne", tags=["Mobile"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([MobileSessionRateThrottle])
def mobile_session_detail(request, token):
    """Return a kiosk pairing session and the user's reservations usable from it."""
    payload = _get_mobile_session_payload(token)
    if payload is None:
        return Response({"detail": "Session mobile invalide ou expiree."}, status=status.HTTP_404_NOT_FOUND)

    station_id = payload.get("station_id")
    borne_id = payload.get("borne_id")
    reservations = []
    for reservation in _startable_user_reservations(request.user, timezone.now()):
        serialized = _serialize_reservation(reservation)
        serialized["compatible_station"] = not station_id or str(reservation.emplacement.station_id) == station_id
        serialized["compatible_borne"] = not borne_id or str(reservation.emplacement.borne_id) == borne_id
        serialized["compatible_terminal"] = serialized["compatible_station"] and serialized["compatible_borne"]
        serialized["station_id"] = str(reservation.emplacement.station_id)
        serialized["borne_id"] = str(reservation.emplacement.borne_id)
        reservations.append(serialized)

    return Response(
        {
            "mobile_session": _serialize_mobile_session(payload),
            "reservations": reservations,
        }
    )


@_schema("Autoriser une réservation depuis le mobile", request=OpenApiTypes.OBJECT, tags=["Mobile"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([MobileSessionRateThrottle])
def mobile_session_authorize(request, token):
    """Authorize one user reservation for the kiosk paired with this token."""
    payload = _get_mobile_session_payload(token)
    if payload is None:
        return Response({"detail": "Session mobile invalide ou expiree."}, status=status.HTTP_404_NOT_FOUND)

    reservation_id = request.data.get("reservation_id")
    if not reservation_id:
        return Response({"detail": "reservation_id est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

    reservation = (
        _terminal_reservation_queryset()
        .filter(id_reservation=reservation_id, utilisateur=request.user)
        .first()
    )
    if reservation is None:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    startable_ids = {
        item.id_reservation
        for item in _startable_user_reservations(request.user, timezone.now())
    }
    if reservation.id_reservation not in startable_ids:
        return Response(
            {"detail": "Cette réservation ne peut pas encore être démarrée."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    station_id = payload.get("station_id")
    if station_id and str(reservation.emplacement.station_id) != station_id:
        return Response(
            {
                "detail": "Cette réservation est associée à une autre station.",
                "station": reservation.emplacement.station.nom,
                "station_id": str(reservation.emplacement.station_id),
                "emplacement": reservation.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )
    borne_id = payload.get("borne_id")
    if borne_id and str(reservation.emplacement.borne_id) != borne_id:
        return Response(
            {
                "detail": "Cette réservation est associée à une autre borne.",
                "station": reservation.emplacement.station.nom,
                "station_id": str(reservation.emplacement.station_id),
                "borne": reservation.emplacement.borne.nom,
                "borne_id": str(reservation.emplacement.borne_id),
                "emplacement": reservation.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )

    now = timezone.now()
    payload.update(
        {
            "status": "authorized",
            "authorized_at": now.isoformat(),
            "authorized_by": str(request.user.id_user),
            "authorized_user": request.user.pseudo,
            "reservation_id": str(reservation.id_reservation),
        }
    )
    _store_mobile_session(payload)
    _log_security_event(
        request,
        request.user,
        f"user:{request.user.pseudo}:mobile_session_authorized:{reservation.reference_code}",
    )

    return Response(
        {
            "mobile_session": _serialize_mobile_session(payload),
            "reservation": _serialize_reservation(reservation),
        }
    )


@_schema("Consulter une session mobile depuis le terminal", tags=["Terminal"])
@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_mobile_session_status(request, token):
    """Return the current authorization state for a kiosk/mobile pairing token."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    return _terminal_mobile_session_status_response(token)


@_schema("Consulter une session mobile depuis le terminal", request=OpenApiTypes.OBJECT, tags=["Terminal"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_mobile_session_status_from_body(request):
    """Return a mobile session state using a fixed terminal endpoint."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    token = (request.data.get("token") or "").strip()
    if not token:
        return Response({"detail": "token est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)
    return _terminal_mobile_session_status_response(token)


def _terminal_mobile_session_status_response(token):
    """Build the status response for one mobile session token."""
    payload = _get_mobile_session_payload(token)
    if payload is None:
        return Response({"detail": "Session mobile invalide ou expiree."}, status=status.HTTP_404_NOT_FOUND)

    response = {"mobile_session": _serialize_mobile_session(payload)}
    reservation_id = payload.get("reservation_id")
    if reservation_id:
        reservation = _terminal_reservation_queryset().filter(id_reservation=reservation_id).first()
        if reservation:
            response["reservation"] = _serialize_reservation(reservation)
    return Response(response)


@_schema(
    "Consommer une autorisation mobile depuis le terminal",
    tags=["Terminal"],
    operation_id="terminal_mobile_session_consume_by_token",
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_consume_mobile_session(request, token):
    """Open the charging session authorized from the user's phone."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    return _terminal_consume_mobile_session_response(request, token)


@_schema(
    "Consommer une autorisation mobile depuis le terminal",
    request=OpenApiTypes.OBJECT,
    tags=["Terminal"],
    operation_id="terminal_mobile_session_consume_from_body",
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_consume_mobile_session_from_body(request):
    """Consume a mobile authorization using a fixed terminal endpoint."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    token = (request.data.get("token") or "").strip()
    if not token:
        return Response({"detail": "token est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)
    return _terminal_consume_mobile_session_response(request, token)


def _terminal_consume_mobile_session_response(request, token):
    """Open the charging session authorized for one mobile session token."""
    payload = _get_mobile_session_payload(token)
    if payload is None:
        return Response({"detail": "Session mobile invalide ou expiree."}, status=status.HTTP_404_NOT_FOUND)

    if payload.get("status") not in {"authorized", "consumed"}:
        return Response({"detail": "Session mobile en attente d'autorisation."}, status=status.HTTP_409_CONFLICT)

    reservation = _terminal_reservation_queryset().filter(id_reservation=payload.get("reservation_id")).first()
    if reservation is None:
        return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    now = timezone.now()
    session = _get_reservation_session(reservation)
    session_is_active = session is not None and session.end_time is None
    start_grace = _start_grace_delta()
    end_grace = _end_grace_delta()

    if reservation.statut == "annulee":
        return Response({"detail": "La réservation est annulée."}, status=status.HTTP_400_BAD_REQUEST)
    if reservation.date_debut - start_grace > now and not session_is_active:
        return Response({"detail": "La réservation n'a pas encore commencé."}, status=status.HTTP_400_BAD_REQUEST)
    if reservation.date_fin + end_grace < now and not session_is_active:
        return Response({"detail": "La fenêtre de réservation est expirée."}, status=status.HTTP_400_BAD_REQUEST)

    station_id = payload.get("station_id") or (request.data.get("station_id") or "").strip()
    if station_id and str(reservation.emplacement.station_id) != station_id:
        return Response(
            {
                "detail": "Cette réservation est associée à une autre station.",
                "station": reservation.emplacement.station.nom,
                "station_id": str(reservation.emplacement.station_id),
                "emplacement": reservation.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )
    borne_id = payload.get("borne_id") or (request.data.get("borne_id") or "").strip()
    if borne_id and str(reservation.emplacement.borne_id) != borne_id:
        return Response(
            {
                "detail": "Cette réservation est associée à une autre borne.",
                "station": reservation.emplacement.station.nom,
                "station_id": str(reservation.emplacement.station_id),
                "borne": reservation.emplacement.borne.nom,
                "borne_id": str(reservation.emplacement.borne_id),
                "emplacement": reservation.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )

    conflict_response = _session_start_conflict_response(reservation, now)
    if conflict_response is not None:
        return conflict_response

    session, created = ChargingSession.objects.get_or_create(
        reservation=reservation,
        defaults={
            "emplacement": reservation.emplacement,
            "start_time": now,
        },
    )
    try:
        mark_access_validated(session, now=now)
    except ChargeSessionStateError:
        return Response(
            {"detail": CHARGE_SESSION_STATE_ERROR_DETAIL},
            status=status.HTTP_409_CONFLICT,
        )

    if reservation.statut != "active":
        reservation.statut = "active"
        reservation.save(update_fields=["statut"])

    if payload.get("status") != "consumed":
        payload.update(
            {
                "status": "consumed",
                "consumed_at": now.isoformat(),
                "session_id": str(session.id_session),
            }
        )
        _store_mobile_session(payload)

    return Response(
        {
            "message": "Autorisation mobile consommee.",
            "session_created": created,
            "mobile_session": _serialize_mobile_session(payload),
            "session": _serialize_session(session),
        }
    )


@_schema("Synchroniser le cache offline d'une borne", tags=["Terminal"])
@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_offline_cache(request):
    """Return near-term reservations a kiosk may validate locally if backend is down."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    station_id = (request.query_params.get("station_id") or "").strip()
    borne_id = (request.query_params.get("borne_id") or "").strip()
    now = timezone.now()
    horizon = now + timedelta(hours=OFFLINE_CACHE_HORIZON_HOURS)
    end_grace = _end_grace_delta()
    queryset = (
        _terminal_reservation_queryset()
        .filter(
            statut__in=["confirmee", "active"],
            date_fin__gte=now - end_grace,
            date_debut__lte=horizon,
            authentification__isnull=False,
            authentification__is_active=True,
        )
        .order_by("date_debut", "id_reservation")
    )
    if station_id:
        queryset = queryset.filter(emplacement__station_id=station_id)
    if borne_id:
        queryset = queryset.filter(emplacement__borne_id=borne_id)

    return Response(
        {
            "generated_at": now.isoformat(),
            "expires_at": horizon.isoformat(),
            "station_id": station_id,
            "borne_id": borne_id,
            "start_grace_minutes": RESERVATION_START_GRACE_MINUTES,
            "end_grace_minutes": RESERVATION_END_GRACE_MINUTES,
            "results": [_serialize_offline_cached_reservation(reservation) for reservation in queryset],
        }
    )


@_schema("Synchroniser les evenements offline d'une borne", request=OpenApiTypes.OBJECT, tags=["Terminal"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_offline_events(request):
    """Reconcile locally accepted kiosk events after a backend outage."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    events = request.data.get("events")
    station_id = (request.data.get("station_id") or "").strip()
    borne_id = (request.data.get("borne_id") or "").strip()
    if not isinstance(events, list):
        return Response({"detail": "events doit être une liste."}, status=status.HTTP_400_BAD_REQUEST)

    accepted = []
    rejected = []
    for event in events:
        if not isinstance(event, dict):
            rejected.append({"event_id": None, "detail": "Événement invalide."})
            continue

        event_id = event.get("id")
        event_type = event.get("event_type")
        if not event_id:
            rejected.append({"event_id": None, "detail": "id evenement manquant."})
            continue
        if event_type != "offline_session_started":
            rejected.append({"event_id": event_id, "detail": "Type evenement non supporte."})
            continue

        result, error = _reconcile_offline_session_started(request, event, station_id, borne_id=borne_id)
        if error:
            rejected.append({"event_id": event_id, "detail": error})
        else:
            accepted.append(result)

    return Response(
        {
            "accepted": accepted,
            "rejected": rejected,
            "synced_event_ids": [item["event_id"] for item in accepted if item.get("event_id")],
        },
        status=status.HTTP_207_MULTI_STATUS if rejected else status.HTTP_200_OK,
    )


@_schema("Authentifier un accès depuis le terminal", request=OpenApiTypes.OBJECT, tags=["Terminal"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_authenticate(request):
    """Validate terminal access credentials and open a charging session."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    reservation_id = request.data.get("reservation_id")
    reservation_code = (request.data.get("reservation_code") or "").strip().upper()
    auth_mode = (request.data.get("auth_mode") or "").strip().lower()
    auth_value = (request.data.get("auth_value") or "").strip()
    station_id = (request.data.get("station_id") or "").strip()
    borne_id = (request.data.get("borne_id") or "").strip()
    parsed_qr = _parse_qr_payload(auth_value)
    if parsed_qr:
        reservation_code = reservation_code or parsed_qr["reservation_code"]
        auth_mode = auth_mode or "qr"
        auth_value = parsed_qr["token"]
    now = timezone.now()

    direct_rfid = auth_mode == "rfid" and auth_value and not (reservation_id or reservation_code)
    if direct_rfid:
        auth_method, reservation, error_response = _resolve_direct_rfid_reservation(auth_value, now)
        if error_response is not None:
            return error_response
    else:
        if not (reservation_id or reservation_code) or not auth_mode or not auth_value:
            return Response({"detail": "reservation_code (ou reservation_id), auth_mode et auth_value sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)

        reservation_qs = _terminal_reservation_queryset()
        if reservation_code:
            reservation = reservation_qs.filter(reference_code=reservation_code).first()
        else:
            reservation = reservation_qs.filter(id_reservation=reservation_id).first()
        if reservation is None:
            return Response({"detail": "Réservation introuvable."}, status=status.HTTP_404_NOT_FOUND)
        auth_method = reservation.authentification

    if reservation.statut == "annulee":
        return Response({"detail": "La réservation est annulée."}, status=status.HTTP_400_BAD_REQUEST)

    session = _get_reservation_session(reservation)
    session_is_active = session is not None and session.end_time is None
    start_grace = _start_grace_delta()
    end_grace = _end_grace_delta()

    if reservation.date_debut - start_grace > now and not session_is_active:
        return Response({"detail": "La réservation n'a pas encore commencé."}, status=status.HTTP_400_BAD_REQUEST)

    if reservation.date_fin + end_grace < now and not session_is_active:
        return Response({"detail": "La fenêtre de réservation est expirée."}, status=status.HTTP_400_BAD_REQUEST)

    expected_mode = reservation.auth_choice
    if expected_mode != auth_mode:
        return Response({"detail": "Mauvais moyen d'authentification."}, status=status.HTTP_400_BAD_REQUEST)

    if auth_method is None:
        return Response({"detail": "Aucun moyen d'authentification associé à cette réservation."}, status=status.HTTP_400_BAD_REQUEST)
    if auth_mode == "code" and _sms_access_is_locked(auth_method):
        return Response(
            {"detail": "Code SMS temporaire verrouillé après trop d'essais."},
            status=status.HTTP_423_LOCKED,
        )
    if not auth_method.is_active:
        return Response({"detail": "Le moyen d'authentification est révoqué."}, status=status.HTTP_400_BAD_REQUEST)

    if auth_method.expiration and auth_method.expiration + end_grace < now and not session_is_active:
        return Response({"detail": "Le moyen d'authentification est expire."}, status=status.HTTP_400_BAD_REQUEST)

    if station_id and str(reservation.emplacement.station_id) != station_id:
        return Response(
            {
                "detail": "Cette réservation est associée à une autre station.",
                "station": reservation.emplacement.station.nom,
                "station_id": str(reservation.emplacement.station_id),
                "emplacement": reservation.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )
    if borne_id and str(reservation.emplacement.borne_id) != borne_id:
        return Response(
            {
                "detail": "Cette réservation est associée à une autre borne.",
                "station": reservation.emplacement.station.nom,
                "station_id": str(reservation.emplacement.station_id),
                "borne": reservation.emplacement.borne.nom,
                "borne_id": str(reservation.emplacement.borne_id),
                "emplacement": reservation.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )

    conflict_response = _session_start_conflict_response(reservation, now)
    if conflict_response is not None:
        return conflict_response

    provided_hash = _hash_secret(auth_value)
    if not direct_rfid and provided_hash != auth_method.hash_valeur:
        if auth_mode == "code":
            if _record_sms_access_failure(auth_method):
                return Response(
                    {"detail": "Code SMS temporaire verrouillé après trop d'essais."},
                    status=status.HTTP_423_LOCKED,
                )
        return Response({"detail": "Authentification refusée."}, status=status.HTTP_401_UNAUTHORIZED)

    if auth_mode == "code":
        _reset_sms_access_failures(auth_method)

    session, created = ChargingSession.objects.get_or_create(
        reservation=reservation,
        defaults={
            "emplacement": reservation.emplacement,
            "start_time": now,
        },
    )
    try:
        mark_access_validated(session, now=now)
    except ChargeSessionStateError:
        return Response(
            {"detail": CHARGE_SESSION_STATE_ERROR_DETAIL},
            status=status.HTTP_409_CONFLICT,
        )

    if reservation.statut != "active":
        reservation.statut = "active"
        reservation.save(update_fields=["statut"])

    if auth_mode in {"qr", "code"}:
        auth_method.expiration = session.start_time + timedelta(minutes=DEFAULT_SESSION_MAX_MINUTES)
        auth_method.metadata = {
            **(auth_method.metadata or {}),
            "session_started_at": session.start_time.isoformat(),
            "session_max_minutes": DEFAULT_SESSION_MAX_MINUTES,
        }
        auth_method.save(update_fields=["expiration", "metadata"])

    return Response(
        {
            "message": "Authentification réussie.",
            "session_created": created,
            "session": _serialize_session(session),
            "auth_expiration": auth_method.expiration.isoformat() if auth_method.expiration else None,
        }
    )


@_schema("Clôturer une session de charge depuis le terminal", request=OpenApiTypes.OBJECT, tags=["Terminal"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TerminalRateThrottle])
def terminal_stop_session(request):
    """Close the active charging session after the ESP32 confirms a stop command."""
    secret_error = _terminal_secret_response(request)
    if secret_error is not None:
        return secret_error

    session_id = (request.data.get("session_id") or "").strip()
    station_id = (request.data.get("station_id") or "").strip()
    if not session_id:
        return Response({"detail": "session_id est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

    session = (
        ChargingSession.objects.select_related("reservation", "emplacement", "emplacement__station", "emplacement__borne")
        .filter(id_session=session_id)
        .first()
    )
    if session is None:
        return Response({"detail": "Session introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if station_id and str(session.emplacement.station_id) != station_id:
        return Response(
            {
                "detail": "Cette session est associée à une autre station.",
                "station": session.emplacement.station.nom,
                "station_id": str(session.emplacement.station_id),
                "emplacement": session.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )
    borne_id = (request.data.get("borne_id") or "").strip()
    if borne_id and str(session.emplacement.borne_id) != borne_id:
        return Response(
            {
                "detail": "Cette session est associée à une autre borne.",
                "station": session.emplacement.station.nom,
                "station_id": str(session.emplacement.station_id),
                "borne": session.emplacement.borne.nom,
                "borne_id": str(session.emplacement.borne_id),
                "emplacement": session.emplacement.numero,
            },
            status=status.HTTP_409_CONFLICT,
        )

    mark_stop_requested(session)
    closed = _close_charging_session(session)
    session.refresh_from_db()

    return Response(
        {
            "message": "Session de charge clôturée." if closed else "Session de charge déjà clôturée.",
            "session_closed": closed,
            "session": _serialize_session(session),
        }
    )
