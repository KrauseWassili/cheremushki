from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import TelegramInvite


@admin.register(TelegramInvite)
class TelegramInviteAdmin(ModelAdmin):
    list_display = (
        "user",
        "used",
        "telegram_user_id",
        "profile_message_id",
        "reminder_count",
        "created_at",
        "used_at",
    )
    list_filter = ("used",)
    search_fields = ("user__email", "invite_link", "telegram_user_id")
    readonly_fields = (
        "created_at",
        "used_at",
        "profile_posted_at",
        "profile_synced_at",
        "telegram_user_id",
    )
