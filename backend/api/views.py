from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Emplacement, ProfilUtilisateur, Reservation, Session as ChargingSession, Station
from .permissions import IsStaffUser
from .serializers import (
    AdminUserUpdateSerializer,
    AdminUserSerializer,
    EmplacementSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    RegisterSerializer,
    StationSerializer,
)

User = get_user_model()


def _serialize_user(user):
    return {
        "id": str(user.id_user),
        "pseudo": user.pseudo,
        "email": user.email,
        "telephone": user.telephone,
        "statut": user.statut,
        "nom": getattr(getattr(user, "profil", None), "nom", ""),
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def _get_or_create_profile(user):
    profile, _created = ProfilUtilisateur.objects.get_or_create(
        utilisateur=user,
        defaults={"nom": user.pseudo},
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

    active_session = sessions_qs.filter(end_time__isnull=True).first()

    past_sessions = sessions_qs.filter(end_time__isnull=False)

    return Response(
        {
            "user": _serialize_user(request.user),
            "stats": {
                "sessions_total": sessions_qs.count(),
                "active_sessions": sessions_qs.filter(end_time__isnull=True).count(),
                "past_sessions": past_sessions.count(),
            },
            "active_session": _serialize_session(active_session) if active_session else None,
            "recharge_history": [
                _serialize_session(session)
                for session in sessions_qs[:5]
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
                for user in User.objects.select_related("profil").order_by("-date_joined")[:5]
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
        users = User.objects.select_related("profil").order_by("-date_joined")
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
            telephone=payload.get("telephone", ""),
            statut=payload.get("statut", "actif"),
            is_staff=is_staff,
        )
    else:
        user = User.objects.create_user(
            pseudo=payload["pseudo"],
            email=payload["email"],
            password=payload["password"],
            telephone=payload.get("telephone", ""),
            statut=payload.get("statut", "actif"),
            is_staff=is_staff,
            is_superuser=False,
        )
    profile_name = payload.get("nom") or payload["pseudo"]
    ProfilUtilisateur.objects.create(utilisateur=user, nom=profile_name)
    return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsStaffUser])
def admin_user_detail(request, user_id):
    try:
        user = User.objects.select_related("profil").get(id_user=user_id)
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


def privacy(request):
    return render(
        request,
        "api/simple_page.html",
        {
            "title": "Politique de confidentialite",
            "description": (
                "Consultez les informations essentielles sur la collecte, l'utilisation "
                "et la protection des donnees liees a l'application."
            ),
        },
    )
