from django.urls import path

from .page_views import cgu, contact, home, login_view, privacy, signup

urlpatterns = [
    path("", home, name="home"),
    path("inscription/", signup, name="signup"),
    path("connexion/", login_view, name="login"),
    path("contact/", contact, name="contact"),
    path("conditions-generales-utilisation/", cgu, name="cgu"),
    path("politique-confidentialite/", privacy, name="privacy"),
]
