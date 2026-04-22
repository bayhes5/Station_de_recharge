from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("api.urls")),
    path("api/", include("api.api_urls")),
    path("admin/", admin.site.urls),
]
