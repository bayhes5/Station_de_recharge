from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import dashboard, login, me, register

urlpatterns = [
    path("register/", register, name="api-register"),
    path("login/", login, name="api-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", me, name="api-me"),
    path("dashboard/", dashboard, name="api-dashboard"),
]
