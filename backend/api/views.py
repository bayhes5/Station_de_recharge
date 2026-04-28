import hashlib
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render
from django.utils import timezone
from django.db import transaction
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


def _serialize_user(user):
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
    profile, _created = ProfilUtilisateur.objects.get_or_create(
        utilisateur=user,
        defaults={"nom": user.pseudo, "telephone": ""},
    )
    return profile


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _serialize_reservation(reservation):
    return {
        "id": str(reservation.id_reservation),
        "reference_code": reservation.reference_code,
        "station": reservation.emplacement.station.nom,
        "emplacement": reservation.emplacement.numero,
        "date_debut": reservation.date_debut.isoformat(),
        "date_fin": reservation.date_fin.isoformat(),
        "statut": reservation.statut,
    }


def _serialize_session(session):
    return {
        "id": str(session.id_session),
        "station": session.emplacement.station.nom,
        "emplacement": session.emplacement.numero,
        "start_time": session.start_time.isoformat(),
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "status": "active" if session.end_time is None else "closed",
    }


def _serialize_station(station):
    return {
        "id_station": str(station.id_station),
        "nom": station.nom,
        "localisation_text": station.localisation_text,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "statut": station.statut,
    }


def _serialize_emplacement(emplacement):
    return {
        "id_emplacement": str(emplacement.id_emplacement),
        "station": str(emplacement.station_id),
        "station_nom": emplacement.station.nom,
        "numero": emplacement.numero,
        "statut": emplacement.statut,
        "lock_state": emplacement.lock_state,
    }


def _serialize_auth_method(method):
    return {
        "id_auth": str(method.id_auth),
        "type_auth": str(method.type_auth_id),
        "type_label": method.type_auth.libelle,
        "display_value": method.display_value,
        "expiration": method.expiration.isoformat() if method.expiration else None,
    }


def _serialize_maintenance(maintenance):
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
    return {
        "id_technicien": str(technician.id_technicien),
        "utilisateur": str(technician.utilisateur_id) if technician.utilisateur_id else None,
        "utilisateur_pseudo": technician.utilisateur.pseudo if technician.utilisateur else None,
        "nom": technician.nom,
        "email": technician.email,
        "telephone": technician.telephone,
    }


def _user_is_technician(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if hasattr(user, "_technician_profile_cache"):
        return user._technician_profile_cache
    exists = Technicien.objects.filter(utilisateur_id=user.id_user).exists()
    user._technician_profile_cache = exists
    return exists


def _generate_reservation_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        if not Reservation.objects.filter(reference_code=code).exists():
            return code
    raise RuntimeError("Impossible de generer un code de reservation unique.")


def _get_type_auth(libelle):
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
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _generate_access_secret(prefix):
    return f"{prefix}-{secrets.token_urlsafe(18)}"


def _ensure_rfid_auth(user, auth_value):
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


def _create_temporary_auth(user, auth_mode):
    type_auth = _get_type_auth(auth_mode)
    clear_value = _generate_access_secret(auth_mode.upper())
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=_hash_secret(clear_value),
        display_value=clear_value,
        expiration=timezone.now() + timedelta(hours=24),
    )
    return auth_method, clear_value


def _reservation_overlaps(emplacement, date_debut, date_fin):
    return Reservation.objects.filter(
        emplacement=emplacement,
        date_debut__lt=date_fin,
        date_fin__gt=date_debut,
        statut__in=["confirmee", "active", "en_attente"],
    ).exists()


def _round_to_thirty_minutes(dt):
    if dt.minute % 30 != 0 or dt.second != 0 or dt.microsecond != 0:
        return False
    return True


def _duration_is_valid(date_debut, date_fin):
    return (date_fin - date_debut) == timedelta(minutes=30)


def home(request):
    return render(
        request,
        "api/home.html",
        {
            "frontend_base_url": settings.FRONTEND_BASE_URL,
        },
    )


def signup(request):
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


@api_view(["GET"])
@permission_classes([AllowAny])
def register_availability(request):
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


@api_view(["POST"])
def register(request):
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


@api_view(["POST"])
def login(request):
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    profile = _get_or_create_profile(request.user)
    return Response(
        {
            "user": _serialize_user(request.user),
            "profile": {
                "nom": profile.nom,
            },
        }
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def profile(request):
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_account(request):
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
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
    upcoming_reservations = reservations_qs.filter(date_debut__gte=timezone.now())
    recent_reservations = reservations_qs[:5]

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


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_overview(request):
    return Response(
        {
            "stats": {
                "users_total": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "stations_total": Station.objects.count(),
                "emplacements_total": Emplacement.objects.count(),
                "reservations_total": Reservation.objects.count(),
                "sessions_total": ChargingSession.objects.count(),
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_users(request):
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


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_user_detail(request, user_id):
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_stations(request):
    if request.method == "GET":
        stations = Station.objects.order_by("nom")
        return Response({"results": [StationSerializer(station).data for station in stations]})

    serializer = StationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    station = serializer.save()
    return Response(StationSerializer(station).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_station_detail(request, station_id):
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_emplacements(request):
    if request.method == "GET":
        emplacements = Emplacement.objects.select_related("station").order_by("station__nom", "numero")
        return Response({"results": [EmplacementSerializer(emplacement).data for emplacement in emplacements]})

    serializer = EmplacementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    emplacement = serializer.save()
    return Response(EmplacementSerializer(emplacement).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_emplacement_detail(request, emplacement_id):
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auth_methods(request):
    if request.method == "GET":
        methods = (
            Authentification.objects.filter(utilisateur=request.user, type_auth__libelle="RFID", is_active=True)
            .exclude(display_value="")
            .select_related("type_auth")
            .order_by("-expiration", "-id_auth")
        )
        return Response({"results": [_serialize_auth_method(method) for method in methods]})

    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_auth_method(request):
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


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_auth_method(request, auth_id):
    deleted, _detail = Authentification.objects.filter(
        id_auth=auth_id,
        utilisateur=request.user,
        type_auth__libelle="RFID",
    ).delete()

    if not deleted:
        return Response({"detail": "Badge RFID introuvable."}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auth_history(request):
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def reservation_availability(request):
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
            {"detail": "Une réservation dure exactement 30 minutes."},
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stations_catalog(request):
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def reservations(request):
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
            {"detail": "Une réservation dure exactement 30 minutes."},
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
    if auth_mode == "rfid":
        auth_method = _get_saved_rfid_auth(request.user)
        if auth_method is None:
            return Response(
                {"auth_value": "Ajoute d'abord un badge RFID dans ton profil."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        auth_method, clear_value = _create_temporary_auth(request.user, auth_mode)

    reservation = Reservation.objects.create(
        utilisateur=request.user,
        emplacement=emplacement,
        reference_code=_generate_reservation_code(),
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
        response["access_payload"] = {
            "mode": auth_mode,
            "value": clear_value,
        }
    response["reservation_code"] = reservation.reference_code
    return Response(response, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def technician_maintenances(request):
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_technicians(request):
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


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_technician_detail(request, technician_id):
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_maintenances(request):
    if request.method == "GET":
        maintenances = Maintenance.objects.select_related("station", "technicien").order_by("-date_planifiee")
        return Response({"results": [MaintenanceAdminSerializer(maintenance).data for maintenance in maintenances]})

    serializer = MaintenanceAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    maintenance = serializer.save()
    return Response(MaintenanceAdminSerializer(maintenance).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_maintenance_detail(request, maintenance_id):
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


@api_view(["POST"])
@permission_classes([AllowAny])
def terminal_authenticate(request):
    reservation_id = request.data.get("reservation_id")
    reservation_code = (request.data.get("reservation_code") or "").strip().upper()
    auth_mode = (request.data.get("auth_mode") or "").strip().lower()
    auth_value = (request.data.get("auth_value") or "").strip()

    if not (reservation_id or reservation_code) or not auth_mode or not auth_value:
        return Response({"detail": "reservation_code (ou reservation_id), auth_mode et auth_value sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)

    reservation_qs = Reservation.objects.select_related("emplacement", "authentification", "authentification__type_auth")
    if reservation_code:
        reservation = reservation_qs.filter(reference_code=reservation_code).first()
    else:
        reservation = reservation_qs.filter(id_reservation=reservation_id).first()
    if reservation is None:
        return Response({"detail": "Reservation introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if reservation.date_debut - timedelta(minutes=15) > timezone.now():
        return Response({"detail": "La reservation n'a pas encore commence."}, status=status.HTTP_400_BAD_REQUEST)

    if reservation.date_fin < timezone.now():
        return Response({"detail": "La réservation est expirée."}, status=status.HTTP_400_BAD_REQUEST)

    expected_mode = reservation.auth_choice
    if expected_mode != auth_mode:
        return Response({"detail": "Mauvais moyen d'authentification."}, status=status.HTTP_400_BAD_REQUEST)

    auth_method = reservation.authentification
    if auth_method is None:
        return Response({"detail": "Aucun moyen d'authentification associe a cette reservation."}, status=status.HTTP_400_BAD_REQUEST)

    provided_hash = _hash_secret(auth_value)
    if provided_hash != auth_method.hash_valeur:
        return Response({"detail": "Authentification refusee."}, status=status.HTTP_401_UNAUTHORIZED)

    session, _created = ChargingSession.objects.get_or_create(
        reservation=reservation,
        defaults={
            "emplacement": reservation.emplacement,
            "start_time": timezone.now(),
        },
    )

    return Response(
        {
            "message": "Authentification reussie.",
            "session": _serialize_session(session),
        }
    )


def privacy(request):
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
