from celery import shared_task
from django.core.cache import cache

from apps.bot.services.telegram import get_updates, process_telegram_update


@shared_task
def poll_telegram_updates_task():
    offset = cache.get("telegram_update_offset")
    updates = get_updates(offset=offset, timeout=0)

    for update in updates:
        cache.set("telegram_update_offset", update["update_id"] + 1, timeout=None)
        process_telegram_update(update)
