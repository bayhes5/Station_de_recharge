from django.shortcuts import render


def home(request):
    return render(request, "api/home.html")


def signup(request):
    return render(
        request,
        "api/simple_page.html",
        {
            "title": "Inscription",
            "description": (
                "Créez votre compte pour réserver un emplacement, suivre vos recharges "
                "et accéder aux services de la station."
            ),
        },
    )


def login_view(request):
    return render(
        request,
        "api/simple_page.html",
        {
            "title": "Connexion",
            "description": (
                "Connectez-vous pour consulter vos sessions de recharge, votre historique "
                "et vos informations utilisateur."
            ),
        },
    )


def contact(request):
    return render(
        request,
        "api/simple_page.html",
        {
            "title": "Contact",
            "description": (
                "Besoin d'aide, d'une information technique ou d'un renseignement sur la "
                "station de recharge ? Cette page est le point d'entrée pour nous joindre."
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
