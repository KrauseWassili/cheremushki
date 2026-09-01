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

    invite_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Zeitpunkt des Einladungsversands. Das Feld verhindert einen zweiten Versand, "
            "auch wenn das Profil erneut gespeichert wird. Nicht durch "
            "invite_link ersetzbar, der Link entsteht auch bei einem Retry, "
            "dessen Mailversand danach scheitert."
        ),
    )

    telegram_user_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="Telegram-User-ID; pro Club-Account nur einmal erlaubt.",
    )
    profile_message_id = models.BigIntegerField(null=True, blank=True)
    profile_chat_id = models.CharField(max_length=64, blank=True, default="")
    profile_thread_id = models.BigIntegerField(null=True, blank=True)
    profile_photo_file_id = models.CharField(max_length=255, blank=True, default="")
    profile_posted_at = models.DateTimeField(null=True, blank=True)
    profile_synced_at = models.DateTimeField(null=True, blank=True)
    profile_content_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=(
            "SHA-256 über Caption, Keyboard und Bild des zuletzt gesendeten "
            "Posts. Stimmt der Hash, entfällt der Telegram-Call komplett."
        ),
    )
    reminder_count = models.PositiveSmallIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Telegram Einladung"
        verbose_name_plural = "Telegram Einladungen"

    def __str__(self):
        return f"{self.user.email} - used={self.used}"


class TelegramForumTopic(models.Model):
    """
    Zuordnung Topic-Name -> message_thread_id der Klub-Gruppe.

    Bewusst in der DB und nicht nur im Cache: Die IDs werden vom Web-Prozess
    entdeckt (Webhook/Polling), aber vom Celery-Worker gebraucht. Ein Cache ist
    prozesslokal oder darf jederzeit leer sein – beides würde die Profilposts
    stilllegen.
    """

    name = models.CharField(max_length=128, unique=True)
    thread_id = models.BigIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Telegram Forum-Topic"
        verbose_name_plural = "Telegram Forum-Topics"

    def __str__(self):
        return f"{self.name} → {self.thread_id}"
