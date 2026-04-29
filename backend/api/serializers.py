from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
import re

from .models import (
    Authentification,
    Emplacement,
    Maintenance,
    ProfilUtilisateur,
    Reservation,
    Station,
    Technicien,
    TypeAuth,
)


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    telephone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = get_user_model()
        fields = ("pseudo", "email", "telephone", "statut", "password")
        extra_kwargs = {
            "telephone": {"required": False, "allow_blank": True},
            "statut": {"required": False},
        }

    def validate_pseudo(self, value):
        if User.objects.filter(pseudo__iexact=value.strip()).exists():
            raise serializers.ValidationError("Ce pseudo est déjà utilisé.")
        return value.strip()

    def validate_email(self, value):
        normalized = User.objects.normalize_email(value.strip())
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("Cette adresse email est déjà utilisée.")
        return normalized

    def validate_password(self, value):
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
        password = validated_data.pop("password")
        telephone = validated_data.pop("telephone", "")
        user = self.Meta.model.objects.create_user(password=password, **validated_data)
        ProfilUtilisateur.objects.create(
            utilisateur=user,
            nom=user.pseudo,
            telephone=telephone,
        )
        return user


class ProfileSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(max_length=255, required=False, allow_blank=True)
    telephone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("id_user", "pseudo", "email", "telephone", "statut", "nom", "is_staff", "is_superuser")
        extra_kwargs = {
            "telephone": {"required": False, "allow_blank": True},
            "statut": {"required": False},
            "is_staff": {"read_only": True},
            "is_superuser": {"read_only": True},
        }

    def update(self, instance, validated_data):
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
        if profile_name is not None or telephone is not None:
            profile.save(update_fields=["nom", "telephone"])

        return instance


class AdminUserUpdateSerializer(ProfileSerializer):
    class Meta(ProfileSerializer.Meta):
        fields = (
            "id_user",
            "pseudo",
            "email",
            "telephone",
            "statut",
            "nom",
            "is_active",
            "is_staff",
            "is_superuser",
        )
        extra_kwargs = {
            "telephone": {"required": False, "allow_blank": True},
            "statut": {"required": False},
            "is_active": {"required": False},
            "is_staff": {"required": False},
            "is_superuser": {"required": False},
        }

    def update(self, instance, validated_data):
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
        if profile_name is not None or telephone is not None:
            profile.save(update_fields=["nom", "telephone"])

        return instance


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Les mots de passe ne correspondent pas."})
        return attrs


class AdminUserSerializer(serializers.ModelSerializer):
    nom = serializers.SerializerMethodField()
    telephone = serializers.SerializerMethodField()
    is_technician = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id_user",
            "pseudo",
            "email",
            "telephone",
            "statut",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "date_joined",
            "nom",
            "is_technician",
        )

    def get_nom(self, obj):
        return getattr(getattr(obj, "profil", None), "nom", "")

    def get_telephone(self, obj):
        return getattr(getattr(obj, "profil", None), "telephone", "")

    def get_is_technician(self, obj):
        return hasattr(obj, "technicien_profile")


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = ("id_station", "nom", "localisation_text", "latitude", "longitude", "statut")


class EmplacementSerializer(serializers.ModelSerializer):
    station_nom = serializers.CharField(source="station.nom", read_only=True)

    class Meta:
        model = Emplacement
        fields = ("id_emplacement", "station", "station_nom", "numero", "statut", "lock_state")
        extra_kwargs = {
            "station": {"required": True},
        }


class AuthMethodSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="type_auth.libelle", read_only=True)

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
            "display_value": {"read_only": True},
            "metadata": {"read_only": True},
        }


class ReservationSerializer(serializers.ModelSerializer):
    station_nom = serializers.CharField(source="emplacement.station.nom", read_only=True)
    emplacement_numero = serializers.IntegerField(source="emplacement.numero", read_only=True)
    utilisateur_pseudo = serializers.CharField(source="utilisateur.pseudo", read_only=True)
    auth_mode = serializers.CharField(source="auth_choice", read_only=True)
    auth_type = serializers.CharField(source="authentification.type_auth.libelle", read_only=True)
    auth_display_value = serializers.CharField(source="authentification.display_value", read_only=True)
    auth_expiration = serializers.DateTimeField(source="authentification.expiration", read_only=True)
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
            "authentification",
            "auth_mode",
            "auth_type",
            "auth_display_value",
            "auth_expiration",
            "date_debut",
            "date_fin",
            "statut",
            "can_cancel",
        )
        extra_kwargs = {
            "utilisateur": {"read_only": True},
            "authentification": {"read_only": True},
        }

    def get_can_cancel(self, obj):
        return obj.statut not in {"annulee", "terminee"} and obj.date_debut > timezone.now()


class ReservationCreateSerializer(serializers.Serializer):
    station = serializers.UUIDField(required=False)
    emplacement = serializers.UUIDField()
    date_debut = serializers.DateTimeField()
    date_fin = serializers.DateTimeField(required=False)
    auth_mode = serializers.ChoiceField(choices=("rfid", "qr", "code"))
    auth_value = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        attrs["date_fin"] = attrs["date_debut"] + timedelta(minutes=30)
        return attrs


class TechnicianMaintenanceSerializer(serializers.ModelSerializer):
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

    def get_emplacement_count(self, obj):
        return obj.station.emplacements.count()


class TechnicianSerializer(serializers.ModelSerializer):
    utilisateur_pseudo = serializers.CharField(source="utilisateur.pseudo", read_only=True)

    class Meta:
        model = Technicien
        fields = (
            "id_technicien",
            "utilisateur",
            "utilisateur_pseudo",
            "nom",
            "email",
            "telephone",
        )
        extra_kwargs = {
            "utilisateur": {"required": False, "allow_null": True},
        }


class MaintenanceAdminSerializer(serializers.ModelSerializer):
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
