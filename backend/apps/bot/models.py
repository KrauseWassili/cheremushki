from django.db import models

from apps.accounts.models import CustomUser


class TelegramInvite(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="telegram_invite"
    )
    invite_link = models.URLField(max_length=255, unique=True, blank=True, null=True)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Telegram Einladung"
        verbose_name_plural = "Telegram Einladungen"

    def __str__(self):
        return f"{self.user.email} - used={self.used}"