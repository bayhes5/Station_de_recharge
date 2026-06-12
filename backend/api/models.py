import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserStatus(models.TextChoices):
    """Allowed lifecycle states for application accounts."""

    ACTIVE = "actif", "Actif"
    SUSPENDED = "suspendu", "Suspendu"
    ARCHIVED = "archive", "Archivé"


class ConsentType(models.TextChoices):
    """Consent categories tracked for accountability."""

    CGU = "cgu", "Conditions générales d'utilisation"
    PRIVACY = "politique_confidentialite", "Politique de confidentialité"
    NOTIFICATIONS = "notifications", "Notifications optionnelles"


class ConsentStatus(models.TextChoices):
    """Allowed consent decisions stored in the consent history."""

    ACCEPTED = "accepte", "Accepté"
    REFUSED = "refuse", "Refusé"


class SecurityLogStatus(models.TextChoices):
    """Outcome values for security audit events."""

    SUCCESS = "success", "Succès"
    FAILURE = "failure", "Échec"


class StationStatus(models.TextChoices):
    """Operational lifecycle values for a charging station."""

    ACTIVE = "active", "Active"
    MAINTENANCE = "maintenance", "Maintenance"
    INACTIVE = "inactive", "Inactive"


class BorneStatus(models.TextChoices):
    """Operational lifecycle values for one physical kiosk/charging cabinet."""

    ACTIVE = "active", "Active"
    MAINTENANCE = "maintenance", "Maintenance"
    INACTIVE = "inactive", "Inactive"


class EmplacementStatus(models.TextChoices):
    """Availability values for one charging bay."""

    AVAILABLE = "disponible", "Disponible"
    RESERVED = "reserve", "Réservé"
    OCCUPIED = "occupe", "Occupé"
    MAINTENANCE = "maintenance", "Maintenance"


class LockState(models.TextChoices):
    """Physical lock states reported or controlled by the station."""

    LOCKED = "verrouille", "Verrouillé"
    UNLOCKED = "deverrouille", "Déverrouillé"
    BLOCKED = "bloque", "Bloqué"


class ReservationAuthChoice(models.TextChoices):
    """Authentication modes available for a reservation."""

    RFID = "rfid", "RFID"
    QR = "qr", "QR code"
    CODE = "code", "Code SMS temporaire"


class ReservationStatus(models.TextChoices):
    """Lifecycle values for reservations."""

    PENDING = "en_attente", "En attente"
    CONFIRMED = "confirmee", "Confirmée"
    ACTIVE = "active", "Active"
    CANCELLED = "annulee", "Annulée"
    COMPLETED = "terminee", "Terminée"


class ChargeSessionState(models.TextChoices):
    """Backend lifecycle values for one effective charging session."""

    RESERVED = "reserved", "Réservée"
    ACCESS_VALIDATED = "access_validated", "Accès validé"
    WAITING_PLUG = "waiting_plug", "En attente de branchement"
    CHARGING = "charging", "Charge en cours"
    STOPPING = "stopping", "Arrêt en cours"
    STOPPED = "stopped", "Arrêtée"
    ERROR = "error", "Erreur"


class DeviceType(models.TextChoices):
    """Supported embedded device families."""

    ESP32 = "ESP32", "ESP32"


class DeviceStatus(models.TextChoices):
    """Last business state received from an embedded device."""

    PROVISIONED = "provisioned", "Provisionné"
    ONLINE = "online", "Disponible"
    IDLE = "idle", "Disponible"
    OFFLINE = "offline", "Hors ligne"
    CHARGING = "charging", "Charge en cours"
    ERROR = "error", "Erreur"


class FirmwareUpdateStatus(models.TextChoices):
    """Lifecycle values for firmware compliance and OTA preparation."""

    UNKNOWN = "unknown", "Non renseigne"
    UP_TO_DATE = "up_to_date", "A jour"
    UPDATE_REQUIRED = "update_required", "Mise a jour requise"
    UPDATE_SCHEDULED = "update_scheduled", "Mise a jour planifiee"
    UPDATING = "updating", "Mise a jour en cours"
    FAILED = "failed", "Echec de mise a jour"


class AlertSeverity(models.TextChoices):
    """Severity scale used by operational alerts."""

    LOW = "basse", "Basse"
    MEDIUM = "moyenne", "Moyenne"
    HIGH = "haute", "Haute"
    CRITICAL = "critical", "Critique"
    CRITIQUE = "critique", "Critique"


class AlertStatus(models.TextChoices):
    """Lifecycle values for operational alerts."""

    NEW = "nouvelle", "Nouvelle"
    ACTIVE = "active", "Active"
    IN_PROGRESS = "prise_en_charge", "Prise en charge"
    RESOLVED = "resolue", "Résolue"
    CLOSED = "closed", "Fermée"
    FERMEE = "fermee", "Fermée"


class MaintenanceStatus(models.TextChoices):
    """Lifecycle values for maintenance interventions."""

    PLANNED = "planifiee", "Planifiée"
    IN_PROGRESS = "en_cours", "En cours"
    DONE = "realisee", "Réalisée"
    CANCELLED = "annulee", "Annulée"


class TechnicianStationRole(models.TextChoices):
    """Operational responsibility levels for a technician on one station."""

    REFERENT = "referent", "Référent"
    INTERVENANT = "intervenant", "Intervenant"
    OBSERVATEUR = "observateur", "Observateur"


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
    statut = models.CharField(
        max_length=50, choices=UserStatus.choices, default=UserStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    must_change_password = models.BooleanField(default=False)
    password_reset_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UtilisateurManager()

    USERNAME_FIELD = "pseudo"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "utilisateur"
        constraints = [
            models.CheckConstraint(
                condition=Q(statut__in=UserStatus.values),
                name="chk_user_statut",
            ),
        ]
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
    telephone_verifie = models.BooleanField(default=False)

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
    type = models.CharField(max_length=100, choices=ConsentType.choices)
    statut = models.CharField(max_length=50, choices=ConsentStatus.choices)
    date_consentement = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "consentement"
        constraints = [
            models.CheckConstraint(
                condition=Q(type__in=ConsentType.values),
                name="chk_consent_type",
            ),
            models.CheckConstraint(
                condition=Q(statut__in=ConsentStatus.values),
                name="chk_consent_statut",
            ),
        ]
        indexes = [
            models.Index(
                fields=["utilisateur", "date_consentement"],
                name="idx_consent_user_date",
            ),
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
    statut = models.CharField(max_length=50, choices=SecurityLogStatus.choices)
    date_action = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "journal_securite"
        constraints = [
            models.CheckConstraint(
                condition=Q(statut__in=SecurityLogStatus.values),
                name="chk_log_statut",
            ),
        ]
        indexes = [
            models.Index(
                fields=["utilisateur", "date_action"], name="idx_log_user_date"
            ),
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
            models.Index(
                fields=["utilisateur", "type_auth", "is_active"],
                name="idx_auth_user_type",
            ),
            models.Index(fields=["expiration"], name="idx_auth_expiration"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["type_auth", "hash_valeur"],
                condition=Q(is_active=True) & ~Q(hash_valeur="pending"),
                name="uniq_active_auth_type_secret",
            ),
        ]


class Station(models.Model):
    """Represent a physical charging station and its public location data."""

    id_station = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100)
    localisation_text = models.CharField(max_length=255, db_column="localisation")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    statut = models.CharField(max_length=50, choices=StationStatus.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "station"
        constraints = [
            models.CheckConstraint(
                condition=Q(statut__in=StationStatus.values),
                name="chk_station_statut",
            ),
        ]
        indexes = [
            models.Index(fields=["nom"], name="idx_station_nom"),
            models.Index(fields=["statut"], name="idx_station_statut"),
        ]

    def __str__(self):
        """Return the station name."""
        return self.nom


class Borne(models.Model):
    """Represent one physical charging cabinet attached to a station."""

    id_borne = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="bornes",
        db_column="id_station",
    )
    numero = models.PositiveIntegerField()
    nom = models.CharField(max_length=100)
    terminal_code = models.CharField(max_length=120, blank=True, default="")
    mqtt_prefix = models.CharField(max_length=120, blank=True, default="")
    statut = models.CharField(max_length=50, choices=BorneStatus.choices, default=BorneStatus.ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "borne"
        unique_together = ("station", "numero")
        constraints = [
            models.CheckConstraint(
                condition=Q(statut__in=BorneStatus.values),
                name="chk_borne_statut",
            ),
            models.UniqueConstraint(
                fields=["terminal_code"],
                condition=~Q(terminal_code=""),
                name="uniq_borne_terminal_code",
            ),
        ]
        indexes = [
            models.Index(fields=["station", "statut"], name="idx_borne_station_statut"),
            models.Index(fields=["terminal_code"], name="idx_borne_terminal_code"),
            models.Index(fields=["mqtt_prefix"], name="idx_borne_mqtt_prefix"),
        ]

    @classmethod
    def default_for_station(cls, station):
        """Return the default cabinet used by compatibility flows."""
        borne, _created = cls.objects.get_or_create(
            station=station,
            numero=1,
            defaults={
                "nom": "Borne 1",
                "statut": BorneStatus.ACTIVE,
            },
        )
        return borne

    def __str__(self):
        """Return a readable station and cabinet identifier."""
        return f"{self.station.nom} - borne {self.numero}"


class Emplacement(models.Model):
    """Represent a numbered charging bay within a physical cabinet."""

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
    borne = models.ForeignKey(
        Borne,
        on_delete=models.CASCADE,
        related_name="emplacements",
        db_column="id_borne",
        blank=True,
    )
    numero = models.PositiveIntegerField()
    statut = models.CharField(
        max_length=50, choices=EmplacementStatus.choices, db_column="etat"
    )
    lock_state = models.CharField(
        max_length=50, choices=LockState.choices, db_column="statut_cadenas"
    )

    class Meta:
        db_table = "emplacement"
        unique_together = ("borne", "numero")
        constraints = [
            models.CheckConstraint(
                condition=Q(statut__in=EmplacementStatus.values),
                name="chk_emp_statut",
            ),
            models.CheckConstraint(
                condition=Q(lock_state__in=LockState.values),
                name="chk_emp_lock_state",
            ),
        ]
        indexes = [
            models.Index(fields=["station", "statut"], name="idx_emp_station_statut"),
            models.Index(fields=["borne", "statut"], name="idx_emp_borne_statut"),
            models.Index(fields=["lock_state", "statut"], name="idx_emp_lock_state"),
        ]

    def save(self, *args, **kwargs):
        """Keep the denormalized station field aligned with the parent cabinet."""
        if self.borne_id:
            self.station = self.borne.station
        elif self.station_id:
            self.borne = Borne.default_for_station(self.station)
        super().save(*args, **kwargs)

    def __str__(self):
        """Return a readable station and bay identifier."""
        return f"{self.station.nom} - borne {self.borne.numero} - emplacement {self.numero}"


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
    auth_choice = models.CharField(
        max_length=20,
        choices=ReservationAuthChoice.choices,
        default=ReservationAuthChoice.QR,
    )
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    statut = models.CharField(max_length=50, choices=ReservationStatus.choices)

    class Meta:
        db_table = "reservation"
        constraints = [
            models.CheckConstraint(
                condition=Q(date_fin__gt=models.F("date_debut")),
                name="reservation_date_fin_gt_debut",
            ),
            models.CheckConstraint(
                condition=Q(auth_choice__in=ReservationAuthChoice.values),
                name="chk_res_auth_choice",
            ),
            models.CheckConstraint(
                condition=Q(statut__in=ReservationStatus.values),
                name="chk_res_statut",
            ),
        ]
        indexes = [
            models.Index(
                fields=["emplacement", "date_debut", "date_fin"],
                name="idx_reservation_emp_dates",
            ),
            models.Index(
                fields=["utilisateur", "date_debut"], name="idx_res_user_date"
            ),
            models.Index(fields=["statut", "date_debut"], name="idx_res_statut_date"),
            models.Index(fields=["date_debut", "date_fin"], name="idx_res_dates"),
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
    charge_state = models.CharField(
        max_length=50,
        choices=ChargeSessionState.choices,
        default=ChargeSessionState.RESERVED,
    )
    charge_state_updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "charging_session"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__isnull=True)
                | Q(end_time__gt=models.F("start_time")),
                name="session_end_gt_start",
            ),
            models.CheckConstraint(
                condition=Q(charge_state__in=ChargeSessionState.values),
                name="chk_session_charge_state",
            ),
        ]
        indexes = [
            models.Index(fields=["emplacement"], name="idx_session_emplacement"),
            models.Index(fields=["start_time"], name="idx_session_start"),
            models.Index(fields=["end_time"], name="idx_session_end"),
            models.Index(fields=["start_time", "end_time"], name="idx_session_window"),
            models.Index(fields=["charge_state", "end_time"], name="idx_session_charge_state"),
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
    type_device = models.CharField(max_length=50, choices=DeviceType.choices)
    firmware_version = models.CharField(max_length=50)
    expected_firmware_version = models.CharField(max_length=50, blank=True, default="")
    firmware_update_status = models.CharField(
        max_length=50,
        choices=FirmwareUpdateStatus.choices,
        default=FirmwareUpdateStatus.UNKNOWN,
    )
    ota_update_url = models.URLField(blank=True, default="")
    ota_target_version = models.CharField(max_length=50, blank=True, default="")
    ota_requested_at = models.DateTimeField(null=True, blank=True)
    ota_completed_at = models.DateTimeField(null=True, blank=True)
    ota_last_error = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    slot_id = models.CharField(max_length=50, blank=True, default="")
    hardware_mac = models.CharField(max_length=50, blank=True, default="")
    mac_address = models.CharField(max_length=50, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=DeviceStatus.choices)
    last_command_id = models.CharField(max_length=100, blank=True, default="")
    last_command_action = models.CharField(max_length=20, blank=True, default="")
    last_command_status = models.CharField(max_length=50, blank=True, default="")
    last_command_message = models.CharField(max_length=255, blank=True, default="")
    last_command_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "device"
        constraints = [
            models.CheckConstraint(
                condition=Q(type_device__in=DeviceType.values),
                name="chk_device_type",
            ),
            models.CheckConstraint(
                condition=Q(status__in=DeviceStatus.values),
                name="chk_device_status",
            ),
            models.CheckConstraint(
                condition=Q(firmware_update_status__in=FirmwareUpdateStatus.values),
                name="chk_device_fw_status",
            ),
        ]
        indexes = [
            models.Index(fields=["slot_id"], name="idx_device_slot_id"),
            models.Index(fields=["hardware_mac"], name="idx_device_hw_mac"),
            models.Index(
                fields=["firmware_update_status"],
                name="idx_device_fw_status",
            ),
            models.Index(
                fields=["expected_firmware_version"],
                name="idx_device_fw_expected",
            ),
            models.Index(fields=["last_seen"], name="idx_device_last_seen"),
            models.Index(fields=["status", "last_seen"], name="idx_device_status_seen"),
            models.Index(fields=["last_command_at"], name="idx_device_last_cmd_at"),
        ]


class DeviceCommandLog(models.Model):
    """Store command acknowledgements received from embedded devices."""

    id_command = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="command_logs",
        db_column="id_device",
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        related_name="device_command_logs",
        db_column="id_session",
        null=True,
        blank=True,
    )
    command_id = models.CharField(max_length=100, blank=True, default="")
    action = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=50, blank=True, default="")
    message = models.CharField(max_length=255, blank=True, default="")
    source = models.CharField(max_length=50, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "device_command_log"
        indexes = [
            models.Index(fields=["device", "timestamp"], name="idx_cmd_device_time"),
            models.Index(fields=["command_id"], name="idx_cmd_command_id"),
            models.Index(fields=["action", "timestamp"], name="idx_cmd_action_time"),
            models.Index(fields=["status", "timestamp"], name="idx_cmd_status_time"),
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
    niveau_severite = models.CharField(max_length=50, choices=AlertSeverity.choices)
    status = models.CharField(max_length=50, choices=AlertStatus.choices)
    timestamp = models.DateTimeField(default=timezone.now, db_column="date")
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    notified_at = models.DateTimeField(null=True, blank=True)
    notification_count = models.PositiveIntegerField(default=0)
    assigned_technician = models.ForeignKey(
        "Technicien",
        on_delete=models.SET_NULL,
        related_name="assigned_alerts",
        db_column="assigned_technician_id",
        null=True,
        blank=True,
    )
    acknowledged_by = models.ForeignKey(
        "Technicien",
        on_delete=models.SET_NULL,
        related_name="acknowledged_alerts",
        db_column="acknowledged_by_id",
        null=True,
        blank=True,
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        "Technicien",
        on_delete=models.SET_NULL,
        related_name="resolved_alerts",
        db_column="resolved_by_id",
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "alerte"
        constraints = [
            models.CheckConstraint(
                condition=Q(niveau_severite__in=AlertSeverity.values),
                name="chk_alert_severity",
            ),
            models.CheckConstraint(
                condition=Q(status__in=AlertStatus.values),
                name="chk_alert_status",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "timestamp"], name="idx_alert_status_time"),
            models.Index(
                fields=["session", "timestamp"], name="idx_alert_session_time"
            ),
            models.Index(fields=["-timestamp"], name="idx_alert_ts"),
            models.Index(
                fields=["niveau_severite", "timestamp"], name="idx_alert_sev_time"
            ),
            models.Index(fields=["type", "timestamp"], name="idx_alert_type_time"),
            models.Index(
                fields=["assigned_technician", "status"],
                name="idx_alert_tech_status",
            ),
        ]


class Technicien(models.Model):
    """Represent a maintenance technician optionally linked to a user account."""

    id_technicien = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column="id_tech"
    )
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


class TechnicienStation(models.Model):
    """Limit a technician's operational scope to assigned stations."""

    id_assignment = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technicien = models.ForeignKey(
        Technicien,
        on_delete=models.CASCADE,
        related_name="station_assignments",
        db_column="id_technicien",
    )
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="technician_assignments",
        db_column="id_station",
    )
    role = models.CharField(
        max_length=50,
        choices=TechnicianStationRole.choices,
        default=TechnicianStationRole.INTERVENANT,
    )
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "technicien_station"
        constraints = [
            models.UniqueConstraint(
                fields=["technicien", "station"],
                name="uq_technicien_station",
            ),
            models.CheckConstraint(
                condition=Q(role__in=TechnicianStationRole.values),
                name="chk_tech_station_role",
            ),
        ]
        indexes = [
            models.Index(fields=["technicien", "is_active"], name="idx_tech_station_tech"),
            models.Index(fields=["station", "is_active"], name="idx_tech_station_station"),
        ]

    def __str__(self):
        """Return a readable technician-station assignment label."""
        return f"{self.technicien.nom} - {self.station.nom}"


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
    status = models.CharField(max_length=50, choices=MaintenanceStatus.choices)
    date_planifiee = models.DateTimeField()
    date_realisee = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "maintenance"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=MaintenanceStatus.values),
                name="chk_maint_status",
            ),
        ]
        indexes = [
            models.Index(
                fields=["technicien", "date_planifiee"], name="idx_maint_tech_date"
            ),
            models.Index(
                fields=["station", "date_planifiee"], name="idx_maint_station_date"
            ),
            models.Index(
                fields=["status", "date_planifiee"], name="idx_maint_status_date"
            ),
        ]
