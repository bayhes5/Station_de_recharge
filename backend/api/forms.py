from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError

from .models import ProfilUtilisateur, Utilisateur


class SignupForm(forms.Form):
    pseudo = forms.CharField(max_length=150, label="Pseudo")
    email = forms.EmailField(label="Email")
    telephone = forms.CharField(max_length=30, required=False, label="Telephone")
    nom = forms.CharField(max_length=255, label="Nom")
    mot_de_passe = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        label="Mot de passe",
    )
    confirmation_mot_de_passe = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        label="Confirmation du mot de passe",
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("mot_de_passe")
        password_confirmation = cleaned_data.get("confirmation_mot_de_passe")

        if password and password_confirmation and password != password_confirmation:
            self.add_error(
                "confirmation_mot_de_passe",
                "Les mots de passe ne correspondent pas.",
            )

        return cleaned_data


class LoginForm(forms.Form):
    identifiant = forms.CharField(
        max_length=254,
        label="Pseudo ou email",
    )
    mot_de_passe = forms.CharField(
        widget=forms.PasswordInput,
        label="Mot de passe",
    )


class UtilisateurCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmation du mot de passe", widget=forms.PasswordInput)
    telephone = forms.CharField(max_length=20, required=False, label="Téléphone")

    class Meta:
        model = Utilisateur
        fields = ("pseudo", "email", "statut", "is_staff", "is_active")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Les mots de passe ne correspondent pas.")

        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
            ProfilUtilisateur.objects.get_or_create(
                utilisateur=user,
                defaults={
                    "nom": user.pseudo,
                    "telephone": self.cleaned_data.get("telephone", ""),
                },
            )

        return user


class UtilisateurChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label="Mot de passe")
    telephone = forms.CharField(max_length=20, required=False, label="Téléphone")

    class Meta:
        model = Utilisateur
        fields = (
            "pseudo",
            "email",
            "statut",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["telephone"].initial = getattr(getattr(self.instance, "profil", None), "telephone", "")

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile, _created = ProfilUtilisateur.objects.get_or_create(
                utilisateur=user,
                defaults={"nom": user.pseudo},
            )
            profile.telephone = self.cleaned_data.get("telephone", "")
            profile.save(update_fields=["telephone"])
        return user
