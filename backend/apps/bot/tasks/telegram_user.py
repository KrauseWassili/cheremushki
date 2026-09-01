"""
Abholen von Telegram-Updates per getUpdates.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from apps.bot.exceptions import TelegramAPIError, TelegramTransportError
from apps.bot.services.telegram import get_updates, process_telegram_update

logger = logging.getLogger(__name__)

OFFSET_CACHE_KEY = "telegram_update_offset"

# Der Lock verhindert überlappende Läufe. Beat feuert nach Intervall, nicht
# nach Fertigstellung: Dauert ein Lauf länger als das Intervall, starten zwei
# Tasks mit demselben Offset und verarbeiten dieselben Updates doppelt – ein
# doppelt verarbeitetes chat_member-Update heißt im schlimmsten Fall ein
# zweiter Profilpost im Kanal.
POLL_LOCK_KEY = "telegram-poll-lock"
POLL_LOCK_TTL_SECONDS = 60


@shared_task
def poll_telegram_updates_task():
    if getattr(settings, "TELEGRAM_UPDATE_MODE", "polling") != "polling":
        return

    if not cache.add(POLL_LOCK_KEY, "1", POLL_LOCK_TTL_SECONDS):
        logger.debug("poll_telegram_updates_task: Lauf läuft noch – übersprungen")
        return

    try:
        _poll_once()
    finally:
        cache.delete(POLL_LOCK_KEY)


def _poll_once() -> None:
    offset = cache.get(OFFSET_CACHE_KEY)

    try:
        updates = get_updates(offset=offset, timeout=0)
    except (TelegramAPIError, TelegramTransportError) as exc:
        logger.warning("getUpdates fehlgeschlagen: %s", exc)
        return

    for update in updates:
        update_id = update.get("update_id")
        try:
            process_telegram_update(update)
        except Exception:
            logger.exception(
                "Telegram-Update %s nicht verarbeitbar – wird übersprungen",
                update_id,
            )

        if update_id is not None:
            cache.set(OFFSET_CACHE_KEY, update_id + 1, timeout=None)
