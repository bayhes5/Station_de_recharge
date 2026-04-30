from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class UtilisateurBackend(ModelBackend):
    """Authenticate users with either their pseudo or email address."""

    def authenticate(self, request, identifiant=None, username=None, email=None, password=None, **kwargs):
        """Return the matching active user when the supplied password is valid."""
        UserModel = get_user_model()
        lookup = (identifiant or username or email or "").strip()

        if not lookup or not password:
            return None

        try:
            user = UserModel.objects.get(
                Q(pseudo__iexact=lookup) | Q(email__iexact=lookup)
            )
        except UserModel.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

    def get_user(self, user_id):
        """Fetch a user by primary key for Django session authentication."""
        UserModel = get_user_model()

        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
