from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Allow access only to authenticated Django staff users."""

    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view):
        """Return whether the request user has staff-level access."""
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
