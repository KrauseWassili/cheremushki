"""
Zugangsprüfung für den Telegram-Webhook.
"""

import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


class IsTelegramWebhook(BasePermission):
    """
    Lässt nur Anfragen mit dem konfigurierten Secret-Header durch.
    """

    def has_permission(self, request, view) -> bool:
        if getattr(settings, "TELEGRAM_UPDATE_MODE", "polling") != "webhook":
            return False

        expected = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or ""
        if not expected:
            return False

        provided = request.headers.get(SECRET_HEADER) or ""
        return secrets.compare_digest(provided, expected)
