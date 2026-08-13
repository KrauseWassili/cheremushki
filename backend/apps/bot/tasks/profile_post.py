import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.bot.exceptions import TelegramAPIError
from apps.bot.models import TelegramInvite
from apps.bot.services.telegram import post_or_update_profile_card
from apps.profiles.models import MemberProfile

logger = logging.getLogger(__name__)

PROFILE_REMINDER_DELAY_SECONDS = 60 * 60 * 24
MAX_PROFILE_REMINDERS = 2

# Der Lock verhindert, dass zwei gleichzeitige Syncs desselben Profils beide
# "noch kein Post vorhanden" sehen und zwei Posts erzeugen. Die TTL liegt über
# dem Request-Timeout der Telegram-Calls, damit ein abgestürzter Worker den
# Lock nicht dauerhaft hält.
PROFILE_POST_LOCK_TTL_SECONDS = 120
PROFILE_POST_LOCK_RETRY_SECONDS = 30
DEFAULT_RETRY_DELAY_SECONDS = 60


def _get_or_create_profile(user: CustomUser) -> MemberProfile:
    try:
        return user.member_profile
    except MemberProfile.DoesNotExist:
        profile = MemberProfile(user=user)
        profile.ensure_unique_slug()
        profile.save()
        return profile


@shared_task(bind=True, max_retries=5, default_retry_delay=DEFAULT_RETRY_DELAY_SECONDS)
def sync_telegram_profile_post(self, user_id: int):
    lock_key = f"telegram-profile-post-lock:{user_id}"
    if not cache.add(lock_key, "1", PROFILE_POST_LOCK_TTL_SECONDS):
        logger.info(
            "sync_telegram_profile_post: user=%s wird bereits synchronisiert – "
            "später erneut",
            user_id,
        )
        raise self.retry(countdown=PROFILE_POST_LOCK_RETRY_SECONDS)

    try:
        _sync_profile_post(self, user_id)
    finally:
        cache.delete(lock_key)


def _sync_profile_post(task, user_id: int) -> None:
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        logger.warning("sync_telegram_profile_post: user=%s existiert nicht", user_id)
        return

    if not user.is_active:
        logger.info(
            "sync_telegram_profile_post: user=%s noch nicht aktiv – skip", user_id
        )
        return

    try:
        invite = TelegramInvite.objects.get(user=user, used=True)
    except TelegramInvite.DoesNotExist:
        logger.info(
            "sync_telegram_profile_post: user=%s hat noch keinen genutzten "
            "Telegram-Invite (Gruppe nicht beigetreten) – skip",
            user_id,
        )
        return

    profile = _get_or_create_profile(user)

    try:
        post_or_update_profile_card(profile, invite)
    except TelegramAPIError as exc:
        # Telegram sagt selbst, wie lange zu warten ist ein pauschaler
        # Fixdelay würde direkt wieder ins Limit laufen.
        logger.warning("Profilpost für user=%s fehlgeschlagen: %s", user_id, exc)
        raise task.retry(
            exc=exc, countdown=exc.retry_after or DEFAULT_RETRY_DELAY_SECONDS
        )
    except Exception as exc:
        logger.exception("Profilpost für user=%s fehlgeschlagen", user_id)
        raise task.retry(exc=exc)

    logger.info(
        "sync_telegram_profile_post: user=%s message_id=%s",
        user_id,
        invite.profile_message_id,
    )


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

    if invite.reminder_count >= MAX_PROFILE_REMINDERS:
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
