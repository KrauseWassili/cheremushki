from adrf.routers import DefaultRouter

from .views import TelegramWebhookViewSet

router = DefaultRouter()

router.register("telegram/webhook", TelegramWebhookViewSet, basename="telegram-webhook")
