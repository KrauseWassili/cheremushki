from django.conf import settings
from rest_framework.permissions import BasePermission


class IsTelegramWebhook(BasePermission):
    def has_permission(self, request, view):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        return secret == settings.TELEGRAM_WEBHOOK_SECRET