from django.urls import path

from .views import contact, home, login_view, privacy, signup

urlpatterns = [
    path("", home, name="home"),
    path("inscription/", signup, name="signup"),
    path("connexion/", login_view, name="login"),
    path("contact/", contact, name="contact"),
    path("politique-confidentialite/", privacy, name="privacy"),
]
