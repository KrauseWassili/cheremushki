"""
Versand der Telegram-Einladung.

Die Einladung ist der Übergang von "registriert" zu "Teil der Gruppe" und
damit der einzige Schritt im Onboarding, der sich nicht zurücknehmen lässt:
Ein verschickter Einladungslink ist einmalig gültig und wanderfähig. Deshalb
sitzen hier zwei Sicherungen das Gate (vollständiges Profil) und der Schutz
gegen Doppelversand.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.bot.models import TelegramInvite
from apps.bot.services.telegram import create_single_use_invite_link
from apps.profiles.models import MemberProfile

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_telegram_invite_email(self, user_id: int):
    try:
        user = CustomUser.objects.select_related("member_profile").get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    if not user.is_active:
        return

    if not _profile_is_complete(user):
        logger.info(
            "send_telegram_invite_email: user=%s Profil unvollständig – "
            "keine Einladung",
            user_id,
        )
        return

    invite_link = _claim_invite(self, user)
    if invite_link is None:
        return

    _send_invite_mail(user, invite_link)


def _profile_is_complete(user: CustomUser) -> bool:
    """Das Gate. Ohne vollständiges Profil keine Einladung.

    Die Prüfung liegt hier zusätzlich zum Serializer, der den Task auslöst:
    Dieser Task läuft auch aus dem Admin, aus der Shell und aus einem Retry
    heraus. Ein Gate, das nur am Auslöser hängt, ist keines.
    """
    try:
        profile = user.member_profile
    except MemberProfile.DoesNotExist:
        return False
    return profile.compute_directory_ready()


def _claim_invite(task, user: CustomUser) -> str | None:
    """Reserviert den Versand und gibt den Einladungslink zurück.

    Returns:
        Den Link, wenn dieser Aufruf den Versand für sich beansprucht hat.
        ``None``, wenn die Einladung schon draußen ist.

    Die Zeile wird mit ``select_for_update`` gesperrt und ``invite_sent_at``
    **vor** dem Mailversand gesetzt. Das ist ein bewusster Kompromiss: Ein
    parallel gestarteter Task sieht das Flag und bricht ab. Der Preis ist, dass
    eine fehlgeschlagene Mail nicht automatisch erneut versandt wird – dafür
    gibt es das Admin. Die Alternative (Flag danach setzen) tauscht diesen Fall
    gegen doppelte Einladungslinks, und das ist der schlechtere Fehler: Ein
    Link zu viel ist ein Zugang zu viel.
    """
    with transaction.atomic():
        invite, _ = TelegramInvite.objects.select_for_update().get_or_create(user=user)

        if invite.invite_sent_at:
            logger.info(
                "send_telegram_invite_email: Einladung für user=%s war bereits "
                "versandt (%s) – kein zweiter Versand",
                user.pk,
                invite.invite_sent_at,
            )
            return None

        if not invite.invite_link:
            try:
                invite.invite_link = create_single_use_invite_link(
                    name=f"user-{user.pk}"
                )
            except Exception as exc:
                # Retry innerhalb der Transaktion: Das Flag ist noch nicht
                # gesetzt, der nächste Versuch beginnt also von vorn.
                raise task.retry(exc=exc)

        invite.invite_sent_at = timezone.now()
        invite.save(update_fields=["invite_link", "invite_sent_at"])
        return invite.invite_link


def _send_invite_mail(user: CustomUser, invite_link: str) -> None:
    html_message = render_to_string(
        "emails/telegram_invite.html",
        {"user": user, "invite_link": invite_link},
    )
    send_mail(
        subject="Приглашение в Telegram-группу Черёмушки",
        message=(
            "Профиль заполнен — добро пожаловать! Вступай в закрытую "
            f"Telegram-группу по ссылке: {invite_link}"
        ),
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
