from django import forms


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
