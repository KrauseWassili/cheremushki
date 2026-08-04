import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.bot.models import TelegramInvite
from apps.bot.services.telegram import post_or_update_profile_card
from apps.profiles.models import MemberProfile

logger = logging.getLogger(__name__)


def _get_or_create_profile(user: CustomUser) -> MemberProfile:
    try:
        return user.member_profile
    except MemberProfile.DoesNotExist:
        profile = MemberProfile(user=user)
        profile.ensure_unique_slug()
        profile.save()
        return profile


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def sync_telegram_profile_post(self, user_id: int):
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    if not user.is_active:
        return

    try:
        invite = TelegramInvite.objects.get(user=user, used=True)
    except TelegramInvite.DoesNotExist:
        return

    profile = _get_or_create_profile(user)

    try:
        post_or_update_profile_card(profile, invite)
    except Exception as exc:
        logger.exception("Profilpost für user=%s fehlgeschlagen", user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_profile_completion_reminder(self, user_id: int):
    try:
        user = CustomUser.objects.select_related("member_profile").get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    try:
        invite = TelegramInvite.objects.get(user=user, used=True)
    except TelegramInvite.DoesNotExist:
        return

    profile = _get_or_create_profile(user)
    if profile.compute_directory_ready():
        return

    if invite.reminder_count >= 2:
        return

    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    profile_url = f"{frontend}/profile"

    text = (
        f"Привет, {user.first_name}!\n\n"
        "Твой профиль уже опубликован в «Наши люди», но пока заполнен не полностью.\n"
        f"Пожалуйста, дополни анкету: {profile_url}"
    )

    # --- Reminder nur per E-Mail
    # Todo Bot reminder
    try:
        html_message = render_to_string(
            "emails/profile_reminder.html",
            {"user": user, "profile_url": profile_url},
        )
        send_mail(
            subject="Дополни свой профиль в клубе",
            message=text,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception as exc:
        raise self.retry(exc=exc)

    invite.reminder_count += 1
    invite.last_reminder_at = timezone.now()
    invite.save(update_fields=["reminder_count", "last_reminder_at"])
