from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password


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
        user = self.Meta.model.objects.create_user(
            password=password,
            **validated_data
        )
        return user
