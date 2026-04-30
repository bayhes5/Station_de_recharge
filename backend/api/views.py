import hashlib
import json
import secrets
from io import BytesIO
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render
from django.utils import timezone
from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Authentification,
    Emplacement,
    Maintenance,
    ProfilUtilisateur,
    Reservation,
    Session as ChargingSession,
    Station,
    Technicien,
    TypeAuth,
)
from .permissions import IsStaffUser
from .serializers import (
    AdminUserUpdateSerializer,
    AdminUserSerializer,
    AuthMethodSerializer,
    EmplacementSerializer,
    MaintenanceAdminSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    RegisterSerializer,
    StationSerializer,
    TechnicianSerializer,
    TechnicianMaintenanceSerializer,
)

User = get_user_model()
RESERVATION_START_GRACE_MINUTES = getattr(settings, "RESERVATION_START_GRACE_MINUTES", 15)
DEFAULT_SESSION_MAX_MINUTES = getattr(settings, "CHARGING_SESSION_MAX_MINUTES", 240)


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


def _as_bool(value):
    """Coerce form-like boolean values from API payloads."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
        "emplacement": reservation.emplacement.numero,
        "emplacement_numero": reservation.emplacement.numero,
        "date_debut": reservation.date_debut.isoformat(),
        "date_fin": reservation.date_fin.isoformat(),
        "statut": reservation.statut,
        "auth_mode": reservation.auth_choice,
        "can_cancel": _reservation_can_be_cancelled(reservation),
    }


def _serialize_session(session):
    """Return a compact representation of a charging session."""
    return {
        "id": str(session.id_session),
        "station": session.emplacement.station.nom,
        "emplacement": session.emplacement.numero,
        "start_time": session.start_time.isoformat(),
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "status": "active" if session.end_time is None else "closed",
    }


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


def _serialize_emplacement(emplacement):
    """Return charging bay details with the parent station label."""
    return {
        "id_emplacement": str(emplacement.id_emplacement),
        "station": str(emplacement.station_id),
        "station_nom": emplacement.station.nom,
        "numero": emplacement.numero,
        "statut": emplacement.statut,
        "lock_state": emplacement.lock_state,
    }


def _serialize_auth_method(method):
    """Return a safe authentication method payload without secret material."""
    return {
        "id_auth": str(method.id_auth),
        "type_auth": str(method.type_auth_id),
        "type_label": method.type_auth.libelle,
        "display_value": method.display_value,
        "expiration": method.expiration.isoformat() if method.expiration else None,
    }


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


def _user_is_technician(user):
    """Return whether the user has an associated technician profile."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if hasattr(user, "_technician_profile_cache"):
        return user._technician_profile_cache
    exists = Technicien.objects.filter(utilisateur_id=user.id_user).exists()
    user._technician_profile_cache = exists
    return exists


def _generate_reservation_code():
    """Generate a short unique reservation reference code."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        if not Reservation.objects.filter(reference_code=code).exists():
            return code
    raise RuntimeError("Impossible de generer un code de reservation unique.")


def _get_type_auth(libelle):
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


def _hash_secret(secret):
    """Hash an access secret before persisting it."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _generate_access_secret(prefix):
    """Generate an opaque temporary access secret with a readable prefix."""
    return f"{prefix}-{secrets.token_urlsafe(18)}"


def _mask_secret(secret):
    """Return a display-safe hint for a secret value."""
    if not secret:
        return ""
    return f"****{secret[-4:]}"


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
<svg x="41%" y="41%" width="18%" height="18%" viewBox="0 0 64 64" role="img" aria-label="Acces securise Metropole Verte">
  <rect x="2" y="2" width="60" height="60" rx="12" fill="#ffffff"/>
  <path d="M32 9c-9 9-15 18-15 27 0 10 7 17 15 17s15-7 15-17C47 27 41 18 32 9Z" fill="#1f8f55"/>
  <path d="M22 36c8-1 15-6 21-17-1 16-8 26-21 30" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
</svg>
"""
    return svg.replace("</svg>", f"{pictogram}</svg>")


def _temporary_auth_metadata(auth_mode, expiration, reservation_code, display_value):
    """Build metadata stored alongside a generated temporary credential."""
    metadata = {
        "version": 1,
        "secret_storage": "sha256",
        "token_hint": display_value,
        "expires_at": expiration.isoformat(),
    }
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
        "value": access_value,
        "display_value": auth_method.display_value if auth_method else "",
        "expires_at": expiration.isoformat(),
    }
    if auth_mode == "qr":
        payload["qr_svg"] = _build_qr_svg(access_value)
        payload["format"] = "reservation_access_v1"
    return payload


def _ensure_rfid_auth(user, auth_value):
    """Create or refresh the saved RFID credential for a user."""
    if not auth_value:
        raise ValueError("auth_value est obligatoire pour RFID.")

    type_auth = _get_type_auth("RFID")
    secret_hash = _hash_secret(auth_value.strip())
    auth_method, created = Authentification.objects.get_or_create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=secret_hash,
        defaults={
            "display_value": auth_value.strip(),
            "expiration": timezone.now() + timedelta(days=3650),
        },
    )
    if created:
        return auth_method

    auth_method.display_value = auth_value.strip()
    auth_method.expiration = timezone.now() + timedelta(days=3650)
    auth_method.save(update_fields=["display_value", "expiration"])
    return auth_method


def _get_saved_rfid_auth(user):
    """Return the latest active saved RFID credential for a user."""
    type_auth = _get_type_auth("RFID")
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


def _create_temporary_auth(user, auth_mode, expiration, reservation_code):
    """Create a temporary QR or code credential for a reservation."""
    type_auth = _get_type_auth(auth_mode)
    clear_value = _generate_access_secret(auth_mode.upper())
    display_value = _mask_secret(clear_value)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=_hash_secret(clear_value),
        display_value=display_value,
        metadata=_temporary_auth_metadata(auth_mode, expiration, reservation_code, display_value),
        expiration=expiration,
    )
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

    clear_value = _generate_access_secret(auth_mode.upper())
    display_value = _mask_secret(clear_value)
    auth_method.type_auth = _get_type_auth(auth_mode)
    auth_method.hash_valeur = _hash_secret(clear_value)
    auth_method.display_value = display_value
    auth_method.metadata = _temporary_auth_metadata(
        auth_mode,
        reservation.date_fin,
        reservation.reference_code,
        display_value,
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


def _get_reservation_session(reservation):
    """Return the charging session linked to a reservation when it exists."""
    try:
        return reservation.session
    except ChargingSession.DoesNotExist:
        return None


def _reservation_overlaps(emplacement, date_debut, date_fin):
    """Return whether a charging bay is already booked in a time window."""
    return Reservation.objects.filter(
        emplacement=emplacement,
        date_debut__lt=date_fin,
        date_fin__gt=date_debut,
        statut__in=["confirmee", "active", "en_attente"],
    ).exists()


def _round_to_thirty_minutes(dt):
    """Return whether a datetime is aligned to a 30-minute boundary."""
    if dt.minute % 30 != 0 or dt.second != 0 or dt.microsecond != 0:
        return False
    return True


def _duration_is_valid(date_debut, date_fin):
    """Return whether the requested reservation duration is exactly 30 minutes."""
    return (date_fin - date_debut) == timedelta(minutes=30)


def home(request):
    """Render the backend landing page with links to the frontend."""
    return render(
        request,
        "api/home.html",
        {
            "frontend_base_url": settings.FRONTEND_BASE_URL,
        },
    )


def signup(request):
    """Render the signup bridge page that redirects users to the frontend."""
    return render(
        request,
        "api/auth_page.html",
        {
            "title": "Inscription",
            "description": (
                "Le formulaire d'inscription est maintenant gere par le frontend "
                "JavaScript, pour garder une seule logique de saisie et d'appel API."
            ),
            "primary_cta_label": "Ouvrir l'inscription",
            "primary_cta_url": f"{settings.FRONTEND_BASE_URL}/register.html",
            "secondary_cta_label": "Ouvrir la connexion",
            "secondary_cta_url": f"{settings.FRONTEND_BASE_URL}/login.html",
        },
    )


@_schema(
    "Verifier la disponibilite d'un pseudo ou d'un email",
    parameters=[
        OpenApiParameter("pseudo", OpenApiTypes.STR, OpenApiParameter.QUERY),
        OpenApiParameter("email", OpenApiTypes.STR, OpenApiParameter.QUERY),
    ],
    tags=["Authentification"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
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


@_schema("Creer un compte utilisateur", request=RegisterSerializer, tags=["Authentification"])
@api_view(["POST"])
def register(request):
    """Create a user account and return an authenticated JWT session."""
    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Utilisateur cree",
                "user": _serialize_user(user),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def login_view(request):
    """Render the login bridge page that redirects users to the frontend."""
    return render(
        request,
        "api/auth_page.html",
        {
            "title": "Connexion",
            "description": (
                "La connexion est prise en charge par le frontend JavaScript, avec "
                "un flux d'authentification centralise cote API."
            ),
            "primary_cta_label": "Ouvrir la connexion",
            "primary_cta_url": f"{settings.FRONTEND_BASE_URL}/login.html",
            "secondary_cta_label": "Ouvrir l'inscription",
            "secondary_cta_url": f"{settings.FRONTEND_BASE_URL}/register.html",
        },
    )


@_schema("Connecter un utilisateur", request=OpenApiTypes.OBJECT, tags=["Authentification"])
@api_view(["POST"])
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

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": _serialize_user(user),
            }
        )

    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@_schema("Lire le profil de l'utilisateur connecte", tags=["Compte"])
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


@_schema("Exporter les donnees du compte", tags=["Compte"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_account(request):
    """Export the authenticated user's account, reservations and audit history."""
    user = request.user
    profile = _get_or_create_profile(user)
    reservations = user.reservations.select_related("emplacement", "emplacement__station").order_by("-date_debut")
    sessions = ChargingSession.objects.filter(reservation__utilisateur=user).select_related(
        "reservation", "emplacement", "emplacement__station"
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
        .select_related("reservation", "emplacement", "emplacement__station")
        .order_by("-start_time")
    )

    reservations_qs = (
        Reservation.objects.filter(utilisateur=request.user)
        .select_related("emplacement", "emplacement__station", "authentification", "authentification__type_auth")
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
            "recent_emplacements": [
                _serialize_emplacement(emplacement)
                for emplacement in Emplacement.objects.select_related("station").order_by("-id_emplacement")[:5]
            ],
        }
    )


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
@_schema("Creer un utilisateur administrateur", request=AdminUserUpdateSerializer, tags=["Administration"], operation_id="admin_users_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_users(request):
    """List users or create a user from the administration API."""
    if request.method == "GET":
        users = User.objects.select_related("profil", "technicien_profile").order_by("-date_joined")
        return Response(
            {
                "results": [AdminUserSerializer(user).data for user in users],
            }
        )

    payload = request.data
    required = ("pseudo", "email", "password")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return Response(
            {"detail": f"Champs manquants: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    is_superuser = _as_bool(payload.get("is_superuser", False))
    is_staff = _as_bool(payload.get("is_staff", False)) or is_superuser

    if is_superuser:
        user = User.objects.create_superuser(
            pseudo=payload["pseudo"],
            email=payload["email"],
            password=payload["password"],
            statut=payload.get("statut", "actif"),
            is_staff=is_staff,
        )
    else:
        user = User.objects.create_user(
            pseudo=payload["pseudo"],
            email=payload["email"],
            password=payload["password"],
            statut=payload.get("statut", "actif"),
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
        serializer = AdminUserUpdateSerializer(instance=user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(AdminUserSerializer(user).data)

    user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@_schema("Lister les stations", tags=["Administration"], operation_id="admin_stations_list", methods=["GET"])
@_schema("Creer une station", request=StationSerializer, tags=["Administration"], operation_id="admin_station_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_stations(request):
    """List stations or create a station from the administration API."""
    if request.method == "GET":
        stations = Station.objects.order_by("nom")
        return Response({"results": [StationSerializer(station).data for station in stations]})

    serializer = StationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    station = serializer.save()
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
        return Response(StationSerializer(station).data)

    station.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@_schema("Lister les emplacements", tags=["Administration"], operation_id="admin_emplacements_list", methods=["GET"])
@_schema("Creer un emplacement", request=EmplacementSerializer, tags=["Administration"], operation_id="admin_emplacement_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_emplacements(request):
    """List charging bays or create one from the administration API."""
    if request.method == "GET":
        emplacements = Emplacement.objects.select_related("station").order_by("station__nom", "numero")
        return Response({"results": [EmplacementSerializer(emplacement).data for emplacement in emplacements]})

    serializer = EmplacementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    emplacement = serializer.save()
    return Response(EmplacementSerializer(emplacement).data, status=status.HTTP_201_CREATED)


@_schema("Lire un emplacement", tags=["Administration"], operation_id="admin_emplacement_retrieve", methods=["GET"])
@_schema("Modifier un emplacement", request=EmplacementSerializer, tags=["Administration"], operation_id="admin_emplacement_update", methods=["PATCH"])
@_schema("Supprimer un emplacement", responses={204: None}, tags=["Administration"], operation_id="admin_emplacement_delete", methods=["DELETE"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_emplacement_detail(request, emplacement_id):
    """Retrieve, update or delete one charging bay from the admin API."""
    try:
        emplacement = Emplacement.objects.select_related("station").get(id_emplacement=emplacement_id)
    except Emplacement.DoesNotExist:
        return Response({"detail": "Emplacement introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(EmplacementSerializer(emplacement).data)

    if request.method == "PATCH":
        serializer = EmplacementSerializer(instance=emplacement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EmplacementSerializer(emplacement).data)

    emplacement.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


def contact(request):
    """Render the informational contact page."""
    return render(
        request,
        "api/simple_page.html",
        {
            "title": "Contact",
            "description": (
                "Besoin d'aide, d'une information technique ou d'un renseignement sur la "
                "station de recharge ? Cette page est le point d'entree pour nous joindre."
            ),
        },
    )


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
        return Response({"results": [_serialize_auth_method(method) for method in methods]})

    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@_schema("Creer un moyen d'authentification", request=OpenApiTypes.OBJECT, tags=["Compte"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_auth_method(request):
    """Create or refresh a saved RFID authentication method for the user."""
    auth_mode = (request.data.get("auth_mode") or request.data.get("type") or "").strip().lower()
    auth_value = (request.data.get("auth_value") or request.data.get("value") or "").strip()

    if auth_mode != "rfid":
        return Response(
            {"detail": "Seul RFID peut etre cree manuellement depuis le profil."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        auth_method = _ensure_rfid_auth(request.user, auth_value)
    except ValueError as error:
        return Response({"auth_value": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "message": "Moyen d'authentification enregistre.",
            "auth_method": _serialize_auth_method(auth_method),
            "clear_value": auth_value,
        },
        status=status.HTTP_201_CREATED,
    )


@_schema("Supprimer un moyen d'authentification", responses={204: None}, tags=["Compte"])
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_auth_method(request, auth_id):
    """Delete a saved RFID authentication method owned by the user."""
    deleted, _detail = Authentification.objects.filter(
        id_auth=auth_id,
        utilisateur=request.user,
        type_auth__libelle="RFID",
    ).delete()

    if not deleted:
        return Response({"detail": "Badge RFID introuvable."}, status=status.HTTP_404_NOT_FOUND)

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

    return Response({"results": history})


@_schema(
    "Lister les emplacements disponibles pour une reservation",
    parameters=[
        OpenApiParameter("station", OpenApiTypes.UUID, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("date_debut", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("date_fin", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=True),
    ],
    tags=["Reservations"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def reservation_availability(request):
    """List charging bays available for one station and time slot."""
    station_id = request.query_params.get("station")
    date_debut = request.query_params.get("date_debut")
    date_fin = request.query_params.get("date_fin")

    if not station_id:
        return Response({"detail": "Le parametre station est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

    if not date_debut or not date_fin:
        return Response({"detail": "Les dates sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        date_debut_dt = datetime.fromisoformat(date_debut.replace("Z", "+00:00"))
        date_fin_dt = datetime.fromisoformat(date_fin.replace("Z", "+00:00"))
    except ValueError:
        return Response({"detail": "Format de date invalide."}, status=status.HTTP_400_BAD_REQUEST)

    if not _round_to_thirty_minutes(date_debut_dt) or not _round_to_thirty_minutes(date_fin_dt):
        return Response(
            {"detail": "Les horaires doivent etre alignes sur des tranches de 30 minutes."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if (date_fin_dt - date_debut_dt) != timedelta(minutes=30):
        return Response(
            {"detail": "Une reservation bloque un emplacement pendant exactement 30 minutes."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    station = Station.objects.filter(id_station=station_id).first()
    if not station:
        return Response({"detail": "Station introuvable."}, status=status.HTTP_404_NOT_FOUND)

    emplacements = Emplacement.objects.filter(station=station).order_by("numero")
    available = []
    for emplacement in emplacements:
        if not _reservation_overlaps(emplacement, date_debut_dt, date_fin_dt):
            available.append(_serialize_emplacement(emplacement))

    return Response(
        {
            "station": _serialize_station(station),
            "available_emplacements": available,
        }
    )


@_schema("Lister le catalogue des stations", tags=["Stations"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stations_catalog(request):
    """Return stations with their charging bays for reservation screens."""
    stations = Station.objects.prefetch_related("emplacements").order_by("nom")
    return Response(
        {
            "results": [
                {
                    **_serialize_station(station),
                    "emplacements": [
                        _serialize_emplacement(emplacement)
                        for emplacement in station.emplacements.all().order_by("numero")
                    ],
                }
                for station in stations
            ]
        }
    )


@_schema("Lister ou creer des reservations", request=ReservationCreateSerializer, tags=["Reservations"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def reservations(request):
    """List user reservations or create a new reservation with access data."""
    if request.method == "GET":
        queryset = (
            Reservation.objects.filter(utilisateur=request.user)
            .select_related("emplacement", "emplacement__station", "authentification", "authentification__type_auth")
            .order_by("-date_debut")
        )
        return Response({"results": [ReservationSerializer(reservation).data for reservation in queryset]})

    serializer = ReservationCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if not _round_to_thirty_minutes(data["date_debut"]) or not _round_to_thirty_minutes(data["date_fin"]):
        return Response(
            {"detail": "Les horaires doivent etre alignes sur des tranches de 30 minutes."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if (data["date_fin"] - data["date_debut"]) != timedelta(minutes=30):
        return Response(
            {"detail": "Une reservation bloque un emplacement pendant exactement 30 minutes."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    emplacement = Emplacement.objects.select_related("station").filter(id_emplacement=data["emplacement"]).first()
    if not emplacement:
        return Response({"detail": "Emplacement introuvable."}, status=status.HTTP_404_NOT_FOUND)

    station_id = data.get("station")
    if station_id and str(emplacement.station_id) != str(station_id):
        return Response(
            {"detail": "L'emplacement ne correspond pas a la station choisie."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if _reservation_overlaps(emplacement, data["date_debut"], data["date_fin"]):
        return Response(
            {"detail": "Cet emplacement n'est pas disponible sur cette plage horaire."},
            status=status.HTTP_409_CONFLICT,
        )

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
        "message": "Reservation creee.",
        "reservation": ReservationSerializer(reservation).data,
    }
    if clear_value:
        response["access_payload"] = _build_access_payload(
            auth_mode,
            clear_value,
            auth_method,
            data["date_fin"],
        )
    response["reservation_code"] = reservation.reference_code
    return Response(response, status=status.HTTP_201_CREATED)


@_schema("Annuler une reservation", tags=["Reservations"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_reservation(request, reservation_id):
    """Cancel one reservation owned by the authenticated user."""
    try:
        reservation = Reservation.objects.select_related("utilisateur", "emplacement", "emplacement__station").get(
            id_reservation=reservation_id,
            utilisateur=request.user,
        )
    except Reservation.DoesNotExist:
        return Response({"detail": "Reservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if not _cancel_reservation(reservation):
        return Response(
            {"detail": "Cette reservation ne peut plus etre annulee."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(ReservationSerializer(reservation).data)


@_schema("Regenerer l'acces temporaire d'une reservation", tags=["Reservations"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reservation_access_payload(request, reservation_id):
    """Regenerate temporary QR or code access for an active reservation."""
    try:
        reservation = Reservation.objects.select_related(
            "utilisateur",
            "emplacement",
            "emplacement__station",
            "authentification",
            "authentification__type_auth",
        ).get(
            id_reservation=reservation_id,
            utilisateur=request.user,
        )
    except Reservation.DoesNotExist:
        return Response({"detail": "Reservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if reservation.auth_choice not in {"qr", "code"}:
        return Response(
            {"detail": "Cette reservation utilise un badge RFID."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if reservation.statut in {"annulee", "terminee"} or reservation.date_fin < timezone.now():
        return Response(
            {"detail": "L'acces temporaire ne peut plus etre regenere pour cette reservation."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    auth_method, access_value = _refresh_temporary_auth(reservation)
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


@_schema("Annuler une reservation en administration", tags=["Administration"])
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_cancel_reservation(request, reservation_id):
    """Cancel any cancellable reservation from the administration API."""
    try:
        reservation = Reservation.objects.select_related("utilisateur", "emplacement", "emplacement__station").get(
            id_reservation=reservation_id,
        )
    except Reservation.DoesNotExist:
        return Response({"detail": "Reservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if not _cancel_reservation(reservation):
        return Response(
            {"detail": "Cette reservation ne peut plus etre annulee."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(ReservationSerializer(reservation).data)


@_schema("Lister les maintenances du technicien connecte", tags=["Technicien"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def technician_maintenances(request):
    """List maintenance interventions assigned to the current technician."""
    technicien = getattr(request.user, "technicien_profile", None)
    if technicien is None:
        return Response(
            {"detail": "Aucun profil technicien associe a ce compte."},
            status=status.HTTP_404_NOT_FOUND,
        )

    maintenances = (
        Maintenance.objects.filter(technicien=technicien)
        .select_related("station", "technicien")
        .order_by("date_planifiee")
    )
    return Response({"results": [TechnicianMaintenanceSerializer(maintenance).data for maintenance in maintenances]})


@_schema("Lister les techniciens", tags=["Administration"], operation_id="admin_technicians_list", methods=["GET"])
@_schema("Creer un technicien", request=TechnicianSerializer, tags=["Administration"], operation_id="admin_technician_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_technicians(request):
    """List technicians or create a technician from the administration API."""
    if request.method == "GET":
        technicians = Technicien.objects.select_related("utilisateur").order_by("nom")
        return Response({"results": [TechnicianSerializer(technician).data for technician in technicians]})

    serializer = TechnicianSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    utilisateur = None
    utilisateur_id = request.data.get("utilisateur")
    if utilisateur_id:
        utilisateur = User.objects.filter(id_user=utilisateur_id).first()
        if utilisateur is None:
            return Response({"utilisateur": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    technician = Technicien.objects.create(
        utilisateur=utilisateur,
        nom=serializer.validated_data["nom"],
        email=serializer.validated_data["email"],
        telephone=serializer.validated_data.get("telephone", ""),
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
        technician = Technicien.objects.select_related("utilisateur").get(id_technicien=technician_id)
    except Technicien.DoesNotExist:
        return Response({"detail": "Technicien introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(TechnicianSerializer(technician).data)

    if request.method == "DELETE":
        technician.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = TechnicianSerializer(instance=technician, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    utilisateur_id = request.data.get("utilisateur")
    utilisateur = None
    if utilisateur_id:
        utilisateur = User.objects.filter(id_user=utilisateur_id).first()
        if utilisateur is None:
            return Response({"utilisateur": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    technician.nom = serializer.validated_data.get("nom", technician.nom)
    technician.email = serializer.validated_data.get("email", technician.email)
    technician.telephone = serializer.validated_data.get("telephone", technician.telephone)
    if utilisateur is not None:
        technician.utilisateur = utilisateur
    technician.save()

    return Response(TechnicianSerializer(technician).data)


@_schema("Lister les maintenances", tags=["Administration"], operation_id="admin_maintenances_list", methods=["GET"])
@_schema("Creer une maintenance", request=MaintenanceAdminSerializer, tags=["Administration"], operation_id="admin_maintenance_create", methods=["POST"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_maintenances(request):
    """List maintenance records or create one from the admin API."""
    if request.method == "GET":
        maintenances = Maintenance.objects.select_related("station", "technicien").order_by("-date_planifiee")
        return Response({"results": [MaintenanceAdminSerializer(maintenance).data for maintenance in maintenances]})

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


@_schema("Authentifier un acces depuis le terminal", request=OpenApiTypes.OBJECT, tags=["Terminal"])
@api_view(["POST"])
@permission_classes([AllowAny])
def terminal_authenticate(request):
    """Validate terminal access credentials and open a charging session."""
    reservation_id = request.data.get("reservation_id")
    reservation_code = (request.data.get("reservation_code") or "").strip().upper()
    auth_mode = (request.data.get("auth_mode") or "").strip().lower()
    auth_value = (request.data.get("auth_value") or "").strip()
    parsed_qr = _parse_qr_payload(auth_value)
    if parsed_qr:
        reservation_code = reservation_code or parsed_qr["reservation_code"]
        auth_mode = auth_mode or "qr"
        auth_value = parsed_qr["token"]
    now = timezone.now()

    if not (reservation_id or reservation_code) or not auth_mode or not auth_value:
        return Response({"detail": "reservation_code (ou reservation_id), auth_mode et auth_value sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)

    reservation_qs = Reservation.objects.select_related(
        "emplacement",
        "authentification",
        "authentification__type_auth",
        "session",
    )
    if reservation_code:
        reservation = reservation_qs.filter(reference_code=reservation_code).first()
    else:
        reservation = reservation_qs.filter(id_reservation=reservation_id).first()
    if reservation is None:
        return Response({"detail": "Reservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if reservation.statut == "annulee":
        return Response({"detail": "La reservation est annulee."}, status=status.HTTP_400_BAD_REQUEST)

    session = _get_reservation_session(reservation)
    session_is_active = session is not None and session.end_time is None
    start_grace = timedelta(minutes=RESERVATION_START_GRACE_MINUTES)

    if reservation.date_debut - start_grace > now and not session_is_active:
        return Response({"detail": "La reservation n'a pas encore commence."}, status=status.HTTP_400_BAD_REQUEST)

    if reservation.date_fin < now and not session_is_active:
        return Response({"detail": "La fenetre de reservation est expiree."}, status=status.HTTP_400_BAD_REQUEST)

    expected_mode = reservation.auth_choice
    if expected_mode != auth_mode:
        return Response({"detail": "Mauvais moyen d'authentification."}, status=status.HTTP_400_BAD_REQUEST)

    auth_method = reservation.authentification
    if auth_method is None:
        return Response({"detail": "Aucun moyen d'authentification associe a cette reservation."}, status=status.HTTP_400_BAD_REQUEST)

    if auth_method.expiration and auth_method.expiration < now and not session_is_active:
        return Response({"detail": "Le moyen d'authentification est expire."}, status=status.HTTP_400_BAD_REQUEST)

    provided_hash = _hash_secret(auth_value)
    if provided_hash != auth_method.hash_valeur:
        return Response({"detail": "Authentification refusee."}, status=status.HTTP_401_UNAUTHORIZED)

    session, created = ChargingSession.objects.get_or_create(
        reservation=reservation,
        defaults={
            "emplacement": reservation.emplacement,
            "start_time": now,
        },
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
            "message": "Authentification reussie.",
            "session_created": created,
            "session": _serialize_session(session),
            "auth_expiration": auth_method.expiration.isoformat() if auth_method.expiration else None,
        }
    )


def privacy(request):
    """Render the privacy policy page."""
    return render(
        request,
        "api/simple_page.html",
        {
            "title": "Politique de confidentialite",
            "description": (
                "Consultez les informations essentielles sur la collecte, l'utilisation "
                "et la protection des données liées à l’application."
            ),
        },
    )
