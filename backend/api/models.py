import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UtilisateurManager(BaseUserManager):
    """Create and look up users with the pseudo as the login identifier."""

    use_in_migrations = True

    def get_by_natural_key(self, pseudo):
        """Return the user matching Django's configured natural key."""
        return self.get(pseudo=pseudo)

    def create_user(self, pseudo, email, password=None, **extra_fields):
        """Create a regular user with normalized email and hashed password."""
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
        """Create an administrator account with all required staff flags."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Le superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Le superuser doit avoir is_superuser=True.")

        return self.create_user(pseudo, email, password, **extra_fields)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """Represent an application account authenticated by pseudo and email."""

    id_user = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pseudo = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    statut = models.CharField(max_length=50, default="actif")
    created_at = models.DateTimeField(auto_now_add=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UtilisateurManager()

    USERNAME_FIELD = "pseudo"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "utilisateur"
        indexes = [
            models.Index(fields=["is_active"], name="idx_user_is_active"),
            models.Index(fields=["date_joined"], name="idx_user_date_joined"),
        ]

    def __str__(self):
        """Return the pseudo used to identify the account in admin screens."""
        return self.pseudo


class ProfilUtilisateur(models.Model):
    """Store personal profile details that extend the authentication account."""

    id_profil = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="profil",
        db_column="id_user",
    )
    nom = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "profil_utilisateur"

    def __str__(self):
        """Return the profile display name."""
        return self.nom


class Role(models.Model):
    """Describe an application role that can be assigned to users."""

    id_role = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "role"

    def __str__(self):
        """Return the role label."""
        return self.nom


class UtilisateurRole(models.Model):
    """Link a user to a role with the assignment timestamp."""

    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        db_column="id_user",
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="id_role")
    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "utilisateur_role"
        unique_together = ("utilisateur", "role")

    def __str__(self):
        """Return a readable user-role assignment label."""
        return f"{self.utilisateur} - {self.role}"


class Consentement(models.Model):
    """Record a user's consent state for a specific policy or data use."""

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
        indexes = [
            models.Index(fields=["utilisateur", "date_consentement"], name="idx_consent_user_date"),
        ]


class JournalSecurite(models.Model):
    """Store security audit events associated with user activity."""

    id_log = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        related_name="journaux_securite",
        db_column="id_user",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=255)
    ip = models.GenericIPAddressField()
    statut = models.CharField(max_length=50)
    date_action = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "journal_securite"
        indexes = [
            models.Index(fields=["utilisateur", "date_action"], name="idx_log_user_date"),
        ]


class TypeAuth(models.Model):
    """Define a supported authentication method and its assurance level."""

    id_type = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(max_length=50, unique=True)
    factor_level = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "type_auth"

    def __str__(self):
        """Return the authentication method label."""
        return self.libelle


class Authentification(models.Model):
    """Store a reusable or temporary credential linked to a user."""

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
    hash_valeur = models.TextField(db_column="secret_hash")
    display_value = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    expiration = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "auth_method"
        indexes = [
            models.Index(fields=["utilisateur", "type_auth", "is_active"], name="idx_auth_user_type"),
            models.Index(fields=["expiration"], name="idx_auth_expiration"),
        ]


class Station(models.Model):
    """Represent a physical charging station and its public location data."""

    id_station = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100)
    localisation_text = models.CharField(max_length=255, db_column="localisation")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    statut = models.CharField(max_length=50)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "station"
        indexes = [
            models.Index(fields=["nom"], name="idx_station_nom"),
            models.Index(fields=["statut"], name="idx_station_statut"),
        ]

    def __str__(self):
        """Return the station name."""
        return self.nom


class Emplacement(models.Model):
    """Represent a numbered charging bay within a station."""

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
    statut = models.CharField(max_length=50, db_column="etat")
    lock_state = models.CharField(max_length=50, db_column="statut_cadenas")

    class Meta:
        db_table = "emplacement"
        unique_together = ("station", "numero")
        indexes = [
            models.Index(fields=["station", "statut"], name="idx_emp_station_statut"),
        ]

    def __str__(self):
        """Return a readable station and bay identifier."""
        return f"{self.station.nom} - {self.numero}"


class Reservation(models.Model):
    """Reserve a charging bay for one user and one authentication method."""

    id_reservation = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    reference_code = models.CharField(max_length=12, unique=True, null=True, blank=True)
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        related_name="reservations",
        db_column="id_user",
        null=True,
        blank=True,
    )
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="reservations",
        db_column="id_emplacement",
    )
    authentification = models.ForeignKey(
        "Authentification",
        on_delete=models.SET_NULL,
        related_name="reservations",
        db_column="id_auth",
        null=True,
        blank=True,
    )
    auth_choice = models.CharField(max_length=20, default="qr")
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    statut = models.CharField(max_length=50)

    class Meta:
        db_table = "reservation"
        constraints = [
            models.CheckConstraint(condition=Q(date_fin__gt=models.F("date_debut")), name="reservation_date_fin_gt_debut"),
        ]
        indexes = [
            models.Index(fields=["emplacement", "date_debut", "date_fin"], name="idx_reservation_emp_dates"),
            models.Index(fields=["utilisateur", "date_debut"], name="idx_res_user_date"),
            models.Index(fields=["statut", "date_debut"], name="idx_res_statut_date"),
        ]


class Session(models.Model):
    """Track the effective charging session opened from a reservation."""

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
        db_table = "charging_session"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__isnull=True) | Q(end_time__gt=models.F("start_time")),
                name="session_end_gt_start",
            ),
        ]
        indexes = [
            models.Index(fields=["emplacement"], name="idx_session_emplacement"),
            models.Index(fields=["start_time"], name="idx_session_start"),
            models.Index(fields=["end_time"], name="idx_session_end"),
        ]


class SessionTelemetry(models.Model):
    """Store electrical telemetry samples collected during a charging session."""

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
    energie_kwh = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "session_telemetry"
        indexes = [
            models.Index(fields=["session", "timestamp"], name="idx_telemetry_time"),
            models.Index(fields=["-timestamp"], name="idx_session_tel_ts"),
        ]


class Device(models.Model):
    """Describe the embedded device installed on a charging bay."""

    id_device = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emplacement = models.OneToOneField(
        Emplacement,
        on_delete=models.CASCADE,
        related_name="device",
        db_column="id_emplacement",
    )
    type_device = models.CharField(max_length=50)
    firmware_version = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=50, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50)

    class Meta:
        db_table = "device"
        indexes = [
            models.Index(fields=["last_seen"], name="idx_device_last_seen"),
        ]


class Capteur(models.Model):
    """Represent a sensor attached to an embedded charging device."""

    id_capteur = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="capteurs",
        db_column="id_device",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=50)
    unite = models.CharField(max_length=20)

    class Meta:
        db_table = "capteur"
        indexes = [
            models.Index(fields=["type", "device"], name="idx_capteur_type_dev"),
        ]


class CapteurData(models.Model):
    """Store one timestamped value produced by a sensor."""

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
        indexes = [
            models.Index(fields=["capteur", "timestamp"], name="idx_capteur_data_time"),
            models.Index(fields=["-timestamp"], name="idx_capteur_data_ts"),
        ]


class Alerte(models.Model):
    """Capture an operational alert raised from telemetry or a session."""

    id_alerte = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data = models.ForeignKey(
        CapteurData,
        on_delete=models.SET_NULL,
        related_name="alertes",
        db_column="id_data",
        null=True,
        blank=True,
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        related_name="alertes",
        db_column="id_session",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=50)
    message = models.TextField()
    niveau_severite = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    timestamp = models.DateTimeField(default=timezone.now, db_column="date")

    class Meta:
        db_table = "alerte"
        indexes = [
            models.Index(fields=["status", "timestamp"], name="idx_alert_status_time"),
            models.Index(fields=["session", "timestamp"], name="idx_alert_session_time"),
            models.Index(fields=["-timestamp"], name="idx_alert_ts"),
        ]


class Technicien(models.Model):
    """Represent a maintenance technician optionally linked to a user account."""

    id_technicien = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="id_tech")
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.SET_NULL,
        related_name="technicien_profile",
        db_column="id_user",
        null=True,
        blank=True,
    )
    nom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "technicien"

    def __str__(self):
        """Return the technician display name."""
        return self.nom


class Maintenance(models.Model):
    """Plan and track a maintenance intervention on a station."""

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
        indexes = [
            models.Index(fields=["technicien", "date_planifiee"], name="idx_maint_tech_date"),
            models.Index(fields=["station", "date_planifiee"], name="idx_maint_station_date"),
            models.Index(fields=["status", "date_planifiee"], name="idx_maint_status_date"),
        ]
