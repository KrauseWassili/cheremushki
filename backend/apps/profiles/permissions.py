from rest_framework.permissions import BasePermission


class IsActiveAuthenticated(BasePermission):
    """
    Nur eingeloggte und aktivierte Nutzer (Telegram-Gate bestanden).
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
