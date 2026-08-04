from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.accounts.models import CustomUser
from apps.bot.models import TelegramInvite
from apps.bot.services.telegram import create_single_use_invite_link


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_telegram_invite_email(self, user_id: int):
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    if not user.is_active:
        return

    invite, _ = TelegramInvite.objects.get_or_create(user=user)

    if not invite.invite_link:
        try:
            invite.invite_link = create_single_use_invite_link(name=f"user-{user.pk}")
            invite.save(update_fields=["invite_link"])
        except Exception as exc:
            raise self.retry(exc=exc)

    html_message = render_to_string(
        "emails/telegram_invite.html",
        {"user": user, "invite_link": invite.invite_link},
    )
    send_mail(
        subject="Приглашение в Telegram-группу Черёмушки",
        message=(
            "Аккаунт активирован. Вступи в закрытую Telegram-группу по ссылке: "
            f"{invite.invite_link}"
        ),
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
