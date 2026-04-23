from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    admin_emplacement_detail,
    admin_emplacements,
    admin_overview,
    admin_station_detail,
    admin_stations,
    admin_user_detail,
    admin_users,
    change_password,
    dashboard,
    export_account,
    login,
    me,
    profile,
    register,
)

urlpatterns = [
    path("register/", register, name="api-register"),
    path("login/", login, name="api-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", me, name="api-me"),
    path("me/profile/", profile, name="api-profile"),
    path("me/change-password/", change_password, name="api-change-password"),
    path("me/export/", export_account, name="api-export-account"),
    path("dashboard/", dashboard, name="api-dashboard"),
    path("admin/overview/", admin_overview, name="api-admin-overview"),
    path("admin/users/", admin_users, name="api-admin-users"),
    path("admin/users/<uuid:user_id>/", admin_user_detail, name="api-admin-user-detail"),
    path("admin/stations/", admin_stations, name="api-admin-stations"),
    path("admin/stations/<uuid:station_id>/", admin_station_detail, name="api-admin-station-detail"),
    path("admin/emplacements/", admin_emplacements, name="api-admin-emplacements"),
    path(
        "admin/emplacements/<uuid:emplacement_id>/",
        admin_emplacement_detail,
        name="api-admin-emplacement-detail",
    ),
]
