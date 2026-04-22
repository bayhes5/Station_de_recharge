import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, pseudo):
        return self.get(pseudo=pseudo)

    def create_user(self, pseudo, email, password=None, **extra_fields):
        if not pseudo:
            raise ValueError("Le pseudo est obligatoire.")
        if not email:
            raise ValueError("L'email est obligatoire.")

        email = self.normalize_email(email)
        user = self.model(pseudo=pseudo, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, pseudo, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Le superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Le superuser doit avoir is_superuser=True.")

        return self.create_user(pseudo, email, password, **extra_fields)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    id_user = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pseudo = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=30, blank=True)
    statut = models.CharField(max_length=50, default="actif")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UtilisateurManager()

    USERNAME_FIELD = "pseudo"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "utilisateur"

    def __str__(self):
        return self.pseudo


class ProfilUtilisateur(models.Model):
    id_profil = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="profil",
        db_column="id_user",
    )
    nom = models.CharField(max_length=255)

    class Meta:
        db_table = "profil_utilisateur"

    def __str__(self):
        return self.nom


class Role(models.Model):
    id_role = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "role"

    def __str__(self):
        return self.nom


class UtilisateurRole(models.Model):
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        db_column="id_user",
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="id_role")

    class Meta:
        db_table = "utilisateur_role"
        unique_together = ("utilisateur", "role")

    def __str__(self):
        return f"{self.utilisateur} - {self.role}"


class Consentement(models.Model):
    id_consentement = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="consentements",
        db_column="id_user",
    )
    type = models.CharField(max_length=100)
    statut = models.CharField(max_length=50)
    date_consentement = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "consentement"


class JournalSecurite(models.Model):
    id_log = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="journaux_securite",
        db_column="id_user",
    )
    action = models.CharField(max_length=255)
    ip = models.GenericIPAddressField()
    statut = models.CharField(max_length=50)
    date_action = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "journal_securite"


class TypeAuth(models.Model):
    id_type = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(max_length=100, unique=True)
    factor_level = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "type_auth"

    def __str__(self):
        return self.libelle


class Authentification(models.Model):
    id_auth = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="authentifications",
        db_column="id_user",
    )
    type_auth = models.ForeignKey(
        TypeAuth,
        on_delete=models.PROTECT,
        related_name="authentifications",
        db_column="id_type",
    )
    hash_valeur = models.CharField(max_length=255)
    expiration = models.DateTimeField()

    class Meta:
        db_table = "authentification"


class Station(models.Model):
    id_station = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=150)
    localisation_text = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    statut = models.CharField(max_length=50)

    class Meta:
        db_table = "station"

    def __str__(self):
        return self.nom


class Emplacement(models.Model):
    id_emplacement = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="emplacements",
        db_column="id_station",
    )
    numero = models.PositiveIntegerField()
    statut = models.CharField(max_length=50)
    lock_state = models.CharField(max_length=50)

    class Meta:
        db_table = "emplacement"
        unique_together = ("station", "numero")

    def __str__(self):
        return f"{self.station.nom} - {self.numero}"


class Reservation(models.Model):
    id_reservation = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="reservations",
        db_column="id_user",
    )
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="reservations",
        db_column="id_emplacement",
    )
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    statut = models.CharField(max_length=50)

    class Meta:
        db_table = "reservation"


class Session(models.Model):
    id_session = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name="session",
        db_column="id_reservation",
    )
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="sessions",
        db_column="id_emplacement",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "session"


class SessionTelemetry(models.Model):
    id_telemetry = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="telemetries",
        db_column="id_session",
    )
    courant = models.FloatField()
    tension = models.FloatField()
    energie_kwh = models.FloatField(db_column="energie_kWh")
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "session_telemetry"


class Port(models.Model):
    id_port = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="ports",
        db_column="id_emplacement",
    )
    puissance_max = models.FloatField()
    voltage_max = models.FloatField()
    courant_max = models.FloatField()
    statut = models.CharField(max_length=50)

    class Meta:
        db_table = "port"


class Device(models.Model):
    id_device = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="devices",
        db_column="id_emplacement",
    )
    type_device = models.CharField(max_length=100)
    firmware_version = models.CharField(max_length=100)
    last_seen = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50)

    class Meta:
        db_table = "device"


class Capteur(models.Model):
    id_capteur = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="capteurs",
        db_column="id_emplacement",
    )
    type = models.CharField(max_length=100)
    unite = models.CharField(max_length=50)

    class Meta:
        db_table = "capteur"


class CapteurData(models.Model):
    id_data = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capteur = models.ForeignKey(
        Capteur,
        on_delete=models.CASCADE,
        related_name="donnees",
        db_column="id_capteur",
    )
    valeur = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "capteur_data"


class Alerte(models.Model):
    id_alerte = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="alertes",
        db_column="id_emplacement",
    )
    type = models.CharField(max_length=100)
    message = models.TextField()
    niveau_severite = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "alerte"


class Technicien(models.Model):
    id_technicien = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = "technicien"

    def __str__(self):
        return self.nom


class Maintenance(models.Model):
    id_maintenance = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="maintenances",
        db_column="id_station",
    )
    technicien = models.ForeignKey(
        Technicien,
        on_delete=models.CASCADE,
        related_name="maintenances",
        db_column="id_technicien",
    )
    type = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=50)
    date_planifiee = models.DateTimeField()
    date_realisee = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "maintenance"
