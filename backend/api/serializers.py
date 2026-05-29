from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers
import re

from .models import (
    Authentification,
    Borne,
    Consentement,
    Device,
    Emplacement,
    FirmwareUpdateStatus,
    Maintenance,
    ProfilUtilisateur,
    Reservation,
    Station,
    Technicien,
    TechnicienStation,
)
from .reservation_rules import (
    DEFAULT_RESERVATION_DURATION_MINUTES,
    RESERVATION_DURATION_MINUTES,
    default_reservation_end,
    reservation_duration_error_message,
    reservation_duration_is_allowed,
    reservation_duration_minutes,
)
from .services.firmware import expected_firmware_version, firmware_update_required


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Validate and create accounts from the public registration endpoint."""

    telephone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    cgu_accepted = serializers.BooleanField(write_only=True, required=True)
    privacy_policy_accepted = serializers.BooleanField(write_only=True, required=True)
    notifications_accepted = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = get_user_model()
        fields = (
            "pseudo",
            "email",
            "telephone",
            "statut",
            "password",
            "cgu_accepted",
            "privacy_policy_accepted",
            "notifications_accepted",
        )
        extra_kwargs = {
            "telephone": {"required": False, "allow_blank": True},
            "statut": {"required": False},
        }

    def validate_cgu_accepted(self, value):
        """Require explicit acceptance of the terms before account creation."""
        if not value:
            raise serializers.ValidationError("L'acceptation des CGU est obligatoire.")
        return value

    def validate_privacy_policy_accepted(self, value):
        """Require explicit acknowledgement of the privacy policy."""
        if not value:
            raise serializers.ValidationError("La politique de confidentialité doit être acceptée.")
        return value

    def validate_pseudo(self, value):
        """Normalize and ensure pseudo uniqueness."""
        if User.objects.filter(pseudo__iexact=value.strip()).exists():
            raise serializers.ValidationError("Ce pseudo est déjà utilisé.")
        return value.strip()

    def validate_email(self, value):
        """Normalize and ensure email uniqueness."""
        normalized = User.objects.normalize_email(value.strip())
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("Cette adresse email est déjà utilisée.")
        return normalized

    def validate_password(self, value):
        """Apply the project's password complexity rules."""
        pseudo = (self.initial_data.get("pseudo") or "").strip().lower()
        email = (self.initial_data.get("email") or "").strip().lower()
        email_name = email.split("@", 1)[0] if "@" in email else ""

        checks = [
            (len(value) >= 12, "Le mot de passe doit contenir au moins 12 caractères."),
            (re.search(r"[a-z]", value), "Le mot de passe doit contenir une minuscule."),
            (re.search(r"[A-Z]", value), "Le mot de passe doit contenir une majuscule."),
            (re.search(r"\d", value), "Le mot de passe doit contenir un chiffre."),
            (re.search(r"[^A-Za-z0-9]", value), "Le mot de passe doit contenir un caractère spécial."),
        ]

        errors = [message for valid, message in checks if not valid]
        lowered = value.lower()
        if pseudo and pseudo in lowered:
            errors.append("Le mot de passe ne doit pas contenir le pseudo.")
        if email_name and email_name in lowered:
            errors.append("Le mot de passe ne doit pas contenir la partie principale de l’email.")

        if errors:
            raise serializers.ValidationError(errors)

        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create a user account and its profile in one transaction."""
        password = validated_data.pop("password")
        telephone = validated_data.pop("telephone", "")
        validated_data.pop("cgu_accepted")
        validated_data.pop("privacy_policy_accepted")
        notifications_accepted = validated_data.pop("notifications_accepted", False)
        user = self.Meta.model.objects.create_user(password=password, **validated_data)
        ProfilUtilisateur.objects.create(
            utilisateur=user,
            nom=user.pseudo,
            telephone=telephone,
        )
        Consentement.objects.bulk_create(
            [
                Consentement(utilisateur=user, type="cgu", statut="accepte"),
                Consentement(utilisateur=user, type="politique_confidentialite", statut="accepte"),
                Consentement(
                    utilisateur=user,
                    type="notifications",
                    statut="accepte" if notifications_accepted else "refuse",
                ),
            ]
        )
        return user


class ProfileSerializer(serializers.ModelSerializer):
    """Serialize editable account and profile fields for the current user."""

    nom = serializers.CharField(max_length=255, required=False, allow_blank=True)
    telephone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    telephone_verifie = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id_user",
            "pseudo",
            "email",
            "telephone",
            "telephone_verifie",
            "statut",
            "nom",
            "is_staff",
            "is_superuser",
        )
        extra_kwargs = {
            "telephone": {"required": False, "allow_blank": True},
            "statut": {"required": False},
            "is_staff": {"read_only": True},
            "is_superuser": {"read_only": True},
        }

    def update(self, instance, validated_data):
        """Update the user and synchronize the linked profile fields."""
        profile_name = validated_data.pop("nom", None)
        telephone = validated_data.pop("telephone", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if instance.is_superuser:
            instance.is_staff = True

        instance.save()

        profile, _created = ProfilUtilisateur.objects.get_or_create(
            utilisateur=instance,
            defaults={"nom": profile_name or instance.pseudo, "telephone": telephone or ""},
        )
        if profile_name is not None:
            profile.nom = profile_name
        if telephone is not None:
            profile.telephone = telephone
            profile.telephone_verifie = False
        if profile_name is not None or telephone is not None:
            profile.save(update_fields=["nom", "telephone", "telephone_verifie"])

        return instance

    def get_telephone_verifie(self, obj) -> bool:
        """Return whether the current profile phone number is verified."""
        return getattr(getattr(obj, "profil", None), "telephone_verifie", False)


class AdminUserUpdateSerializer(ProfileSerializer):
    """Expose administrative user fields while reusing profile synchronization."""

    telephone_verifie = serializers.BooleanField(required=False)

    class Meta(ProfileSerializer.Meta):
        fields = (
            "id_user",
            "pseudo",
            "email",
            "telephone",
            "telephone_verifie",
            "statut",
            "nom",
            "is_active",
            "is_staff",
            "is_superuser",
            "must_change_password",
            "password_reset_at",
        )
        extra_kwargs = {
            "telephone": {"required": False, "allow_blank": True},
            "statut": {"required": False},
            "is_active": {"required": False},
            "is_staff": {"required": False},
            "is_superuser": {"required": False},
            "must_change_password": {"read_only": True},
            "password_reset_at": {"read_only": True},
        }

    def update(self, instance, validated_data):
        """Update user flags and profile fields from the admin API."""
        profile_name = validated_data.pop("nom", None)
        telephone = validated_data.pop("telephone", None)
        telephone_verifie = validated_data.pop("telephone_verifie", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if instance.is_superuser:
            instance.is_staff = True

        instance.save()

        profile, _created = ProfilUtilisateur.objects.get_or_create(
            utilisateur=instance,
            defaults={"nom": profile_name or instance.pseudo, "telephone": telephone or ""},
        )
        if profile_name is not None:
            profile.nom = profile_name
        if telephone is not None:
            profile.telephone = telephone
            profile.telephone_verifie = False
        if telephone_verifie is not None:
            profile.telephone_verifie = bool(telephone_verifie)
        if profile_name is not None or telephone is not None or telephone_verifie is not None:
            profile.save(update_fields=["nom", "telephone", "telephone_verifie"])

        return instance


class PasswordChangeSerializer(serializers.Serializer):
    """Validate the payload used to change an authenticated user's password."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Ensure the new password and confirmation match."""
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Les mots de passe ne correspondent pas."})
        return attrs


class ConsentPreferenceSerializer(serializers.Serializer):
    """Validate editable consent preferences from the user profile."""

    notifications_accepted = serializers.BooleanField(required=True)


class AdminUserSerializer(serializers.ModelSerializer):
    """Serialize user records for administrative list and detail views."""

    nom = serializers.SerializerMethodField()
    telephone = serializers.SerializerMethodField()
    telephone_verifie = serializers.SerializerMethodField()
    is_technician = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id_user",
            "pseudo",
            "email",
            "telephone",
            "telephone_verifie",
            "statut",
            "is_active",
            "is_staff",
            "is_superuser",
            "must_change_password",
            "password_reset_at",
            "last_login",
            "date_joined",
            "nom",
            "is_technician",
        )

    def get_nom(self, obj):
        """Return the display name stored on the related profile."""
        return getattr(getattr(obj, "profil", None), "nom", "")

    def get_telephone(self, obj):
        """Return the phone number stored on the related profile."""
        return getattr(getattr(obj, "profil", None), "telephone", "")

    def get_telephone_verifie(self, obj) -> bool:
        """Return whether the phone number stored on the related profile is verified."""
        return getattr(getattr(obj, "profil", None), "telephone_verifie", False)

    def get_is_technician(self, obj):
        """Return whether the user is linked to a technician profile."""
        return hasattr(obj, "technicien_profile")


class StationSerializer(serializers.ModelSerializer):
    """Serialize charging station records for catalog and admin views."""

    class Meta:
        model = Station
        fields = ("id_station", "nom", "localisation_text", "latitude", "longitude", "statut")


class BorneSerializer(serializers.ModelSerializer):
    """Serialize physical kiosk/cabinet records with their station label."""

    station_nom = serializers.CharField(source="station.nom", read_only=True)
    emplacements_count = serializers.SerializerMethodField()

    class Meta:
        model = Borne
        fields = (
            "id_borne",
            "station",
            "station_nom",
            "numero",
            "nom",
            "mqtt_prefix",
            "statut",
            "emplacements_count",
        )
        extra_kwargs = {
            "station": {"required": True},
            "statut": {"required": False},
            "mqtt_prefix": {"required": False, "allow_blank": True},
        }

    def get_emplacements_count(self, obj) -> int:
        """Return the number of charging bays attached to the cabinet."""
        return obj.emplacements.count()


class EmplacementSerializer(serializers.ModelSerializer):
    """Serialize charging bay records with their station and cabinet labels."""

    station_nom = serializers.CharField(source="station.nom", read_only=True)
    borne_nom = serializers.CharField(source="borne.nom", read_only=True)
    borne_numero = serializers.IntegerField(source="borne.numero", read_only=True)

    class Meta:
        model = Emplacement
        fields = (
            "id_emplacement",
            "station",
            "station_nom",
            "borne",
            "borne_nom",
            "borne_numero",
            "numero",
            "statut",
            "lock_state",
        )
        extra_kwargs = {
            "station": {"required": False},
            "borne": {"required": False},
        }

    def validate(self, attrs):
        """Derive the station from the selected cabinet and keep both aligned."""
        station = attrs.get("station") or getattr(self.instance, "station", None)
        borne = attrs.get("borne") or getattr(self.instance, "borne", None)

        if borne is not None:
            if station is not None and station != borne.station:
                raise serializers.ValidationError({"borne": "Cette borne n'appartient pas a la station selectionnee."})
            attrs["station"] = borne.station
            return attrs

        if station is None:
            raise serializers.ValidationError({"station": "Une station ou une borne est obligatoire."})

        attrs["borne"] = Borne.default_for_station(station)
        return attrs


class DeviceAdminSerializer(serializers.ModelSerializer):
    """Serialize ESP32 inventory and firmware policy fields for admins."""

    station_nom = serializers.CharField(source="emplacement.station.nom", read_only=True)
    borne_nom = serializers.CharField(source="emplacement.borne.nom", read_only=True)
    borne_numero = serializers.IntegerField(source="emplacement.borne.numero", read_only=True)
    emplacement_numero = serializers.IntegerField(source="emplacement.numero", read_only=True)
    firmware_update_required = serializers.SerializerMethodField()
    effective_expected_firmware_version = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = (
            "id_device",
            "emplacement",
            "station_nom",
            "borne_nom",
            "borne_numero",
            "emplacement_numero",
            "type_device",
            "slot_id",
            "mac_address",
            "hardware_mac",
            "ip_address",
            "status",
            "last_seen",
            "firmware_version",
            "expected_firmware_version",
            "effective_expected_firmware_version",
            "firmware_update_status",
            "firmware_update_required",
            "ota_target_version",
            "ota_update_url",
            "ota_requested_at",
            "ota_completed_at",
            "ota_last_error",
        )
        read_only_fields = (
            "id_device",
            "station_nom",
            "borne_nom",
            "borne_numero",
            "emplacement_numero",
            "last_seen",
            "firmware_version",
            "firmware_update_required",
            "ota_requested_at",
            "ota_completed_at",
        )
        extra_kwargs = {
            "firmware_update_status": {"required": False},
            "expected_firmware_version": {"required": False, "allow_blank": True},
            "ota_target_version": {"required": False, "allow_blank": True},
            "ota_update_url": {"required": False, "allow_blank": True},
            "ota_last_error": {"required": False, "allow_blank": True},
        }

    def validate_firmware_update_status(self, value):
        """Allow admins to edit only operational OTA status values."""
        if value not in FirmwareUpdateStatus.values:
            raise serializers.ValidationError("Statut firmware inconnu.")
        return value

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_firmware_update_required(self, obj) -> bool:
        """Return whether the device firmware differs from the expected version."""
        return firmware_update_required(obj)

    @extend_schema_field(OpenApiTypes.STR)
    def get_effective_expected_firmware_version(self, obj) -> str:
        """Return the device override or global firmware target."""
        return expected_firmware_version(obj)


class AuthMethodSerializer(serializers.ModelSerializer):
    """Serialize stored authentication methods without exposing raw secrets."""

    type_label = serializers.CharField(source="type_auth.libelle", read_only=True)
    display_value = serializers.SerializerMethodField()

    class Meta:
        model = Authentification
        fields = (
            "id_auth",
            "type_auth",
            "type_label",
            "hash_valeur",
            "display_value",
            "metadata",
            "expiration",
        )
        extra_kwargs = {
            "hash_valeur": {"write_only": True},
            "metadata": {"read_only": True},
        }

    def get_display_value(self, obj):
        """Return a safe authentication hint."""
        if obj.type_auth and obj.type_auth.libelle == "RFID":
            return "Badge RFID enregistre"
        return obj.display_value


class ReservationSerializer(serializers.ModelSerializer):
    """Serialize reservations with station, bay and authentication metadata."""

    station_nom = serializers.CharField(source="emplacement.station.nom", read_only=True)
    borne_nom = serializers.CharField(source="emplacement.borne.nom", read_only=True)
    borne_numero = serializers.IntegerField(source="emplacement.borne.numero", read_only=True)
    emplacement_numero = serializers.IntegerField(source="emplacement.numero", read_only=True)
    utilisateur_pseudo = serializers.CharField(source="utilisateur.pseudo", read_only=True)
    auth_mode = serializers.CharField(source="auth_choice", read_only=True)
    auth_type = serializers.CharField(source="authentification.type_auth.libelle", read_only=True)
    auth_display_value = serializers.SerializerMethodField()
    auth_expiration = serializers.DateTimeField(source="authentification.expiration", read_only=True)
    auth_is_active = serializers.BooleanField(source="authentification.is_active", read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = (
            "id_reservation",
            "reference_code",
            "utilisateur",
            "utilisateur_pseudo",
            "emplacement",
            "emplacement_numero",
            "station_nom",
            "borne_nom",
            "borne_numero",
            "authentification",
            "auth_mode",
            "auth_type",
            "auth_display_value",
            "auth_expiration",
            "auth_is_active",
            "date_debut",
            "date_fin",
            "duration_minutes",
            "statut",
            "can_cancel",
        )
        extra_kwargs = {
            "utilisateur": {"read_only": True},
            "authentification": {"read_only": True},
        }

    def get_can_cancel(self, obj):
        """Return whether the reservation can still be cancelled by a user."""
        return obj.statut not in {"annulee", "terminee"} and obj.date_debut > timezone.now()

    def get_duration_minutes(self, obj):
        """Return the reservation duration in minutes."""
        return reservation_duration_minutes(obj.date_debut, obj.date_fin)

    def get_auth_display_value(self, obj):
        """Return an authentication hint without leaking raw RFID identifiers."""
        auth_method = getattr(obj, "authentification", None)
        if not auth_method:
            return ""
        if auth_method.type_auth and auth_method.type_auth.libelle == "RFID":
            return "Badge RFID enregistre"
        return auth_method.display_value


class ReservationCreateSerializer(serializers.Serializer):
    """Validate reservation creation input from the user-facing API."""

    station = serializers.UUIDField()
    emplacement = serializers.UUIDField(required=False)
    date_debut = serializers.DateTimeField()
    date_fin = serializers.DateTimeField(required=False)
    duration_minutes = serializers.IntegerField(
        required=False,
        min_value=min(RESERVATION_DURATION_MINUTES),
        max_value=max(RESERVATION_DURATION_MINUTES),
    )
    auth_mode = serializers.ChoiceField(choices=("rfid", "qr", "code"))
    auth_value = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        """Validate or derive the reservation end from an allowed duration."""
        duration_minutes = attrs.get("duration_minutes")
        if duration_minutes is not None:
            if duration_minutes not in RESERVATION_DURATION_MINUTES:
                raise serializers.ValidationError({"duration_minutes": reservation_duration_error_message()})
            attrs["date_fin"] = attrs["date_debut"] + timedelta(minutes=duration_minutes)
            return attrs

        if not attrs.get("date_fin"):
            attrs["duration_minutes"] = DEFAULT_RESERVATION_DURATION_MINUTES
            attrs["date_fin"] = default_reservation_end(attrs["date_debut"])
            return attrs

        if not reservation_duration_is_allowed(attrs["date_debut"], attrs["date_fin"]):
            raise serializers.ValidationError({"date_fin": reservation_duration_error_message()})
        return attrs


class TechnicianMaintenanceSerializer(serializers.ModelSerializer):
    """Serialize maintenance work visible to the assigned technician."""

    station_nom = serializers.CharField(source="station.nom", read_only=True)
    emplacement_count = serializers.SerializerMethodField()

    class Meta:
        model = Maintenance
        fields = (
            "id_maintenance",
            "station",
            "station_nom",
            "emplacement_count",
            "technicien",
            "type",
            "description",
            "status",
            "date_planifiee",
            "date_realisee",
        )
        extra_kwargs = {
            "station": {"read_only": True},
            "technicien": {"read_only": True},
        }

    def get_emplacement_count(self, obj) -> int:
        """Return the number of charging bays at the maintenance station."""
        return obj.station.emplacements.count()


class TechnicianStationAssignmentSerializer(serializers.ModelSerializer):
    """Serialize station assignments used to scope technician access."""

    technicien_nom = serializers.CharField(source="technicien.nom", read_only=True)
    station_nom = serializers.CharField(source="station.nom", read_only=True)
    station_localisation = serializers.CharField(source="station.localisation_text", read_only=True)
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = TechnicienStation
        fields = (
            "id_assignment",
            "technicien",
            "technicien_nom",
            "station",
            "station_nom",
            "station_localisation",
            "role",
            "role_display",
            "is_active",
            "assigned_at",
        )
        extra_kwargs = {
            "role": {"required": False},
            "is_active": {"required": False},
            "assigned_at": {"read_only": True},
        }

    def get_role_display(self, obj) -> str:
        """Return the localized role label."""
        return obj.get_role_display()

    def validate(self, attrs):
        """Reject duplicate station assignments with a clear API error."""
        technicien = attrs.get("technicien") or getattr(self.instance, "technicien", None)
        station = attrs.get("station") or getattr(self.instance, "station", None)
        if technicien and station:
            duplicate = TechnicienStation.objects.filter(
                technicien=technicien,
                station=station,
            )
            if self.instance is not None:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {"station": "Cette station est déjà affectée à ce technicien."}
                )
        return attrs


class TechnicianSerializer(serializers.ModelSerializer):
    """Serialize technician profiles for administrative management."""

    utilisateur_pseudo = serializers.CharField(source="utilisateur.pseudo", read_only=True)
    assigned_stations = serializers.SerializerMethodField()
    station_scope = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Technicien
        fields = (
            "id_technicien",
            "utilisateur",
            "utilisateur_pseudo",
            "nom",
            "email",
            "telephone",
            "assigned_stations",
            "station_scope",
        )
        extra_kwargs = {
            "utilisateur": {"required": False, "allow_null": True},
        }

    def validate_station_scope(self, value):
        """Ensure every requested station exists before synchronizing scope."""
        station_ids = list(dict.fromkeys(value))
        existing_count = Station.objects.filter(id_station__in=station_ids).count()
        if existing_count != len(station_ids):
            raise serializers.ValidationError("Une ou plusieurs stations sont introuvables.")
        return station_ids

    @extend_schema_field(TechnicianStationAssignmentSerializer(many=True))
    def get_assigned_stations(self, obj):
        """Return active station assignments without broadening technician scope."""
        assignments = getattr(obj, "prefetched_active_station_assignments", None)
        if assignments is None:
            assignments = (
                obj.station_assignments.filter(is_active=True)
                .select_related("station")
                .order_by("station__nom")
            )
        return TechnicianStationAssignmentSerializer(assignments, many=True).data


class MaintenanceAdminSerializer(serializers.ModelSerializer):
    """Serialize maintenance records for administrative CRUD endpoints."""

    station_nom = serializers.CharField(source="station.nom", read_only=True)
    technicien_nom = serializers.CharField(source="technicien.nom", read_only=True)

    class Meta:
        model = Maintenance
        fields = (
            "id_maintenance",
            "station",
            "station_nom",
            "technicien",
            "technicien_nom",
            "type",
            "description",
            "status",
            "date_planifiee",
            "date_realisee",
        )
