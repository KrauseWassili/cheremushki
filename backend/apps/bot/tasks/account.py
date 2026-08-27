"""
Aufräumen der Telegram-Präsenz eines gelöschten Kontos.
"""

import logging

from celery import shared_task

from apps.bot.models import TelegramInvite
from apps.bot.services.telegram import (
    delete_profile_card,
    kick_chat_member,
    revoke_invite_link,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def purge_telegram_presence(self, user_id: int):
    try:
        invite = TelegramInvite.objects.get(user_id=user_id)
    except TelegramInvite.DoesNotExist:
        return

    post_removed = delete_profile_card(invite)

    if invite.telegram_user_id:
        kick_chat_member(invite.telegram_user_id)
    if invite.invite_link:
        revoke_invite_link(invite.invite_link)

    _reset_invite(invite)

    if not post_removed:
        logger.error(
            "purge_telegram_presence: user=%s – Profilpost blieb stehen, "
            "Löschzusage ist offen",
            user_id,
        )


def _reset_invite(invite: TelegramInvite) -> None:
    """
    Setzt den Invite-Zustand zurück, ohne die Zeile zu löschen.

    Entschieden: `telegram_user_id` geht mit. Damit kann sich jemand nach einer
    Löschung mit demselben Telegram-Account neu anmelden.

    Die Duplikat-Sperre in `_reject_duplicate_account` wird dadurch nicht
    geschwächt.
    """
    invite.telegram_user_id = None
    invite.used = False
    invite.used_at = None
    invite.invite_link = None
    # --- Eine Neuanmeldung muss das Profil-Gate erneut durchlaufen.
    invite.invite_sent_at = None
    invite.reminder_count = 0
    invite.last_reminder_at = None
    invite.save(
        update_fields=[
            "telegram_user_id",
            "used",
            "used_at",
            "invite_link",
            "invite_sent_at",
            "reminder_count",
            "last_reminder_at",
        ]
    )
