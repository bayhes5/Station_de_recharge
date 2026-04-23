from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Emplacement, ProfilUtilisateur, Station


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = get_user_model()
        fields = ("pseudo", "email", "telephone", "statut", "password")
        extra_kwargs = {
            "telephone": {"required": False, "allow_blank": True},
            "statut": {"required": False},
        }

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        user = self.Meta.model.objects.create_user(password=password, **validated_data)
        return user


class ProfileSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(max_length=255, required=False, allow_blank=True)

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
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if instance.is_superuser:
            instance.is_staff = True

        instance.save()

        profile, _created = ProfilUtilisateur.objects.get_or_create(
            utilisateur=instance,
            defaults={"nom": profile_name or instance.pseudo},
        )
        if profile_name is not None:
            profile.nom = profile_name
            profile.save(update_fields=["nom"])

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
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if instance.is_superuser:
            instance.is_staff = True

        instance.save()

        profile, _created = ProfilUtilisateur.objects.get_or_create(
            utilisateur=instance,
            defaults={"nom": profile_name or instance.pseudo},
        )
        if profile_name is not None:
            profile.nom = profile_name
            profile.save(update_fields=["nom"])

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
        )

    def get_nom(self, obj):
        return getattr(getattr(obj, "profil", None), "nom", "")


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
