from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Alerte,
    Authentification,
    Capteur,
    CapteurData,
    Consentement,
    Device,
    Emplacement,
    JournalSecurite,
    Maintenance,
    Port,
    ProfilUtilisateur,
    Reservation,
    Role,
    Session,
    SessionTelemetry,
    Station,
    Technicien,
    TypeAuth,
    Utilisateur,
    UtilisateurRole,
)
from .forms import UtilisateurChangeForm, UtilisateurCreationForm


@admin.register(Utilisateur)
class UtilisateurAdmin(BaseUserAdmin):
    form = UtilisateurChangeForm
    add_form = UtilisateurCreationForm

    list_display = ("pseudo", "email", "telephone", "statut", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "statut")
    search_fields = ("pseudo", "email", "telephone")
    ordering = ("pseudo",)

    fieldsets = (
        (None, {"fields": ("pseudo", "email", "password")}),
        ("Informations personnelles", {"fields": ("telephone", "statut")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates importantes", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "pseudo",
                    "email",
                    "telephone",
                    "statut",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

admin.site.register(ProfilUtilisateur)
admin.site.register(Role)
admin.site.register(UtilisateurRole)
admin.site.register(Consentement)
admin.site.register(JournalSecurite)
admin.site.register(TypeAuth)
admin.site.register(Authentification)
admin.site.register(Reservation)
admin.site.register(Session)
admin.site.register(SessionTelemetry)
admin.site.register(Station)
admin.site.register(Emplacement)
admin.site.register(Port)
admin.site.register(Device)
admin.site.register(Capteur)
admin.site.register(CapteurData)
admin.site.register(Alerte)
admin.site.register(Technicien)
admin.site.register(Maintenance)
