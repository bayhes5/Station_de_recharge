from django.conf import settings
from django.contrib.auth import authenticate
from django.shortcuts import render
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Reservation, Session as ChargingSession
from .serializers import RegisterSerializer


def _serialize_user(user):
    return {
        "id": str(user.id_user),
        "pseudo": user.pseudo,
        "email": user.email,
        "telephone": user.telephone,
        "statut": user.statut,
    }


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
    return Response({"user": _serialize_user(request.user)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    now = timezone.now()
    reservations_qs = (
        request.user.reservations.select_related("emplacement", "emplacement__station")
        .order_by("-date_debut")
    )
    sessions_qs = (
        ChargingSession.objects.filter(reservation__utilisateur=request.user)
        .select_related("reservation", "emplacement", "emplacement__station")
        .order_by("-start_time")
    )

    active_session = sessions_qs.filter(end_time__isnull=True).first()

    upcoming_reservations = reservations_qs.filter(date_debut__gte=now)
    past_sessions = sessions_qs.filter(end_time__isnull=False)

    return Response(
        {
            "user": _serialize_user(request.user),
            "stats": {
                "reservations_total": reservations_qs.count(),
                "reservations_upcoming": upcoming_reservations.count(),
                "sessions_total": sessions_qs.count(),
                "active_sessions": sessions_qs.filter(end_time__isnull=True).count(),
                "past_sessions": past_sessions.count(),
            },
            "active_session": _serialize_session(active_session) if active_session else None,
            "upcoming_reservations": [
                _serialize_reservation(reservation)
                for reservation in upcoming_reservations[:3]
            ],
            "recent_reservations": [
                _serialize_reservation(reservation)
                for reservation in reservations_qs[:5]
            ],
            "recent_sessions": [
                _serialize_session(session)
                for session in sessions_qs[:5]
            ],
        }
    )


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
