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
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.accounts.services.email import send_email, ResendError
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

    _send_invite_mail(self, user, invite_link)
    _mark_invite_sent(user)


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
    """Reserviert den Einladungslink und gibt ihn zurück.

    Returns:
        Den Link, wenn für diesen Nutzer noch keine Einladung draußen ist.
        ``None``, wenn die Mail bereits verschickt wurde.

    Die Zeile wird mit ``select_for_update`` gesperrt, damit der Link genau
    einmal entsteht. Das ist der unumkehrbare Schritt: Jeder Aufruf von
    ``createChatInviteLink`` erzeugt einen weiteren gültigen Zugang zur Gruppe.

    ``invite_sent_at`` setzt dagegen erst der Aufrufer, nachdem die Mail
    wirklich draußen ist. Zwei parallele Tasks können dadurch im ungünstigsten
    Fall dieselbe Mail zweimal verschicken – mit demselben
    ``member_limit=1``-Link, also ohne zusätzlichen Zugang. Der umgekehrte
    Tausch (Flag vor dem Versand) kostet bei jedem Fehlschlag des Versands die
    Einladung dauerhaft: Der Nutzer bekommt keine Mail, und jeder spätere
    Anlauf bricht an genau diesem Flag ab.
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
                # Retry innerhalb der Transaktion: Der Link ist noch nicht
                # gespeichert, der nächste Versuch beginnt also von vorn.
                raise task.retry(exc=exc)
            invite.save(update_fields=["invite_link"])

        return invite.invite_link


def _mark_invite_sent(user: CustomUser) -> None:
    """Hält fest, dass die Mail draußen ist.

    Als gefiltertes ``update`` statt Lesen-Ändern-Schreiben: Ein parallel
    gelaufener Task, der schneller war, behält seinen Zeitstempel.
    """
    TelegramInvite.objects.filter(user=user, invite_sent_at__isnull=True).update(
        invite_sent_at=timezone.now()
    )


def _send_invite_mail(task, user: CustomUser, invite_link: str) -> None:
    """Verschickt die Einladung über Resend.

    Wirft weiter, wenn der Versand scheitert – nur so bleibt ``invite_sent_at``
    ungesetzt und ein späterer Anlauf kann dieselbe Einladung erneut zustellen.
    """
    html_message = render_to_string(
        "emails/telegram_invite.html",
        {"user": user, "invite_link": invite_link},
    )
    subject = "Приглашение в Telegram-группу Черёмушки"
    message = (
        "Профиль заполнен — добро пожаловать! Вступай в закрытую "
        f"Telegram-группу по ссылке: {invite_link}"
    )

    try:
        send_email(
            subject=subject,
            message=message,
            html_message=html_message,
            to=user.email,
        )
    except ResendError as exc:
        if exc.retryable:
            raise task.retry(exc=exc)
        logger.error(
            "Einladung für user=%s dauerhaft nicht zustellbar: %s", user.pk, exc
        )
        raise
