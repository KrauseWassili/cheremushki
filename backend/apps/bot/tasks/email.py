"""
Versand der Telegram-Einladung.

Die Einladung ist der Übergang von "registriert" zu "Teil der Gruppe" und
damit der einzige Schritt im Onboarding, der sich nicht zurücknehmen lässt:
Ein verschickter Einladungslink ist einmalig gültig und wanderfähig. Deshalb
sitzen hier zwei Sicherungen: das Gate (vollständiges Profil) und der Schutz
gegen Doppelversand.

Was ein Fehlschlag hinterlässt – und warum nichts freigegeben werden muss:

- ``createChatInviteLink`` scheitert: Die Transaktion um den Claim rollt
  zurück, ``invite_link`` und ``invite_sent_at`` bleiben leer. Bei Telegram
  existiert kein Link, ein späterer Anlauf beginnt von vorn.
- Der Mailversand scheitert: ``invite_link`` ist gespeichert,
  ``invite_sent_at`` bleibt leer. Ein späterer Anlauf verschickt *denselben*
  Link erneut – kein zusätzlicher Zugang zur Gruppe, also nichts zu
  widerrufen.

In beiden Fällen steht ``invite_sent_at`` auf NULL. Genau daran hängt der
Nachholweg: ``trigger_profile_side_effects`` stößt diesen Task bei jedem
Speichern eines vollständigen Profils erneut an, solange
:func:`apps.bot.services.invites.is_invite_pending` gilt – gedrosselt durch
:func:`apps.bot.services.invites.claim_invite_dispatch`, damit ein noch
laufender Task keinen Zwilling bekommt; dazu kommt die Admin-Action
„Telegram-Einladung erneut senden“. Ein Beat-Job ist dafür nicht nötig.
"""

import logging
from typing import NoReturn

from celery import shared_task
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.accounts.services.email import send_email, ResendError
from apps.bot.exceptions import TelegramAPIError, TelegramTransportError
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
                invite_link = create_single_use_invite_link(name=f"user-{user.pk}")
            except (TelegramAPIError, TelegramTransportError) as exc:
                # Abbruch innerhalb der Transaktion: Der Link ist noch nicht
                # gespeichert, der nächste Versuch beginnt also von vorn.
                _retry_or_give_up(task, user, exc)
            else:
                invite.invite_link = invite_link
                invite.save(update_fields=["invite_link"])

        return invite.invite_link


def _retry_or_give_up(
    task, user: CustomUser, exc: TelegramAPIError | TelegramTransportError
) -> NoReturn:
    """Wirft immer: als Celery-Retry oder als dauerhafter Fehler.

    Dauerhafte Fehler (ungültiges Token, Bot ohne Admin-Rechte) würden jeden
    Retry gleich beantworten und nur die Fehlkonfiguration hinter drei
    Warnungen verstecken. Deshalb ``logger.error`` und Abbruch. Verloren ist
    die Einladung damit nicht: ``invite_sent_at`` bleibt leer, das nächste
    Speichern des Profils nach Ablauf der Dispatch-Sperre
    (``INVITE_DISPATCH_DEBOUNCE_SECONDS``) oder sofort die Admin-Action stößt
    sie erneut an.
    """
    if exc.retryable:
        # Bei 429 nennt Telegram die Wartezeit selbst; ohne Angabe greift
        # default_retry_delay.
        retry_after = exc.retry_after if isinstance(exc, TelegramAPIError) else None
        raise task.retry(exc=exc, countdown=retry_after)
    logger.error(
        "Einladungslink für user=%s nicht erzeugbar, dauerhafter Telegram-Fehler "
        "– kein Retry, Konfiguration prüfen: %s",
        user.pk,
        exc,
    )
    raise exc


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
