"""Server-rendered informational pages and frontend bridge pages."""

from django.conf import settings
from django.shortcuts import render


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


def contact(request):
    """Render the informational contact page."""
    return render(
        request,
        "api/privacy.html",
        {
            "title": "Contact",
            "description": (
                "Besoin d'aide, d'une information technique ou d'un renseignement sur la "
                "station de recharge ? Cette page est le point d'entree pour nous joindre."
            ),
        },
    )


def cgu(request):
    """Render the terms of use page."""
    return render(request, "api/cgu.html")


def privacy(request):
    """Render the privacy policy page."""
    return render(
        request,
        "api/privacy.html",
        {
            "title": "Politique de confidentialite",
            "description": (
                "Consultez les informations essentielles sur la collecte, l'utilisation "
                "et la protection des donnees liees a l'application."
            ),
        },
    )
