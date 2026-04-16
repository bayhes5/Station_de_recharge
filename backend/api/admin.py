from django.contrib import admin

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

admin.site.register(Utilisateur)
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
