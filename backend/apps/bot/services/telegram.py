import json
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone

from ..models import TelegramInvite
from .profile_card import (
    build_profile_caption,
    build_profile_keyboard,
    resolve_avatar_bytes,
)

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
PEOPLE_TOPIC_CACHE_KEY = "telegram_people_topic_id"
TOPIC_MAP_CACHE_KEY = "telegram_forum_topic_map"


def _api_post(method: str, data: dict | None = None, files: dict | None = None) -> dict:
    response = requests.post(
        f"{TELEGRAM_API_BASE}/{method}",
        data=data or {},
        files=files,
        timeout=30,
    )
    payload = response.json() if response.content else {}
    if not response.ok or not payload.get("ok"):
        description = payload.get("description") or response.text
        raise RuntimeError(
            f"Telegram {method} fehlgeschlagen "
            f"(HTTP {response.status_code}): {description}"
        )
    return payload["result"]


def create_single_use_invite_link(name: str) -> str:
    result = _api_post(
        "createChatInviteLink",
        data={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "name": name,
            "member_limit": 1,
        },
    )
    return result["invite_link"]


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    params: dict[str, Any] = {
        "timeout": timeout,
        "allowed_updates": json.dumps(
            ["chat_member", "message", "channel_post", "my_chat_member"]
        ),
    }
    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        f"{TELEGRAM_API_BASE}/getUpdates", params=params, timeout=timeout + 10
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API Fehler: {data}")
    return data["result"]


def remember_forum_topic(name: str, thread_id: int) -> None:
    topic_map = cache.get(TOPIC_MAP_CACHE_KEY) or {}
    topic_map[name] = thread_id
    cache.set(TOPIC_MAP_CACHE_KEY, topic_map, timeout=None)

    expected = getattr(settings, "TELEGRAM_PEOPLE_TOPIC_NAME", "Наши люди")
    if name.strip().lower() == expected.strip().lower():
        cache.set(PEOPLE_TOPIC_CACHE_KEY, thread_id, timeout=None)
        logger.info("Telegram people topic resolved dynamically: %s", thread_id)


def process_forum_topic_message(message: dict) -> None:
    """Discover forum topic IDs from service messages."""
    created = message.get("forum_topic_created")
    edited = message.get("forum_topic_edited")
    thread_id = message.get("message_thread_id")
    if not thread_id:
        return

    if created and created.get("name"):
        remember_forum_topic(created["name"], thread_id)
    elif edited and edited.get("name"):
        remember_forum_topic(edited["name"], thread_id)


def resolve_people_topic_id() -> int | None:
    cached = cache.get(PEOPLE_TOPIC_CACHE_KEY)
    if cached is not None:
        return int(cached)

    configured = getattr(settings, "TELEGRAM_PEOPLE_TOPIC_ID", "") or ""
    if str(configured).strip():
        topic_id = int(configured)
        cache.set(PEOPLE_TOPIC_CACHE_KEY, topic_id, timeout=None)
        return topic_id

    expected = getattr(settings, "TELEGRAM_PEOPLE_TOPIC_NAME", "Наши люди")
    topic_map = cache.get(TOPIC_MAP_CACHE_KEY) or {}
    for name, thread_id in topic_map.items():
        if str(name).strip().lower() == expected.strip().lower():
            cache.set(PEOPLE_TOPIC_CACHE_KEY, int(thread_id), timeout=None)
            return int(thread_id)

    # Best-effort: some Telegram endpoints expose forum topics unofficially.
    try:
        response = requests.get(
            f"{TELEGRAM_API_BASE}/getForumTopics",
            params={"chat_id": settings.TELEGRAM_CHAT_ID, "limit": 100},
            timeout=15,
        )
        payload = response.json() if response.content else {}
        if payload.get("ok"):
            topics = payload.get("result", {}).get("topics") or payload.get(
                "result", []
            )
            for topic in topics:
                name = topic.get("name") or ""
                thread_id = topic.get("message_thread_id") or topic.get("message_id")
                if not thread_id:
                    continue
                remember_forum_topic(name, int(thread_id))
                if name.strip().lower() == expected.strip().lower():
                    return int(thread_id)
    except Exception:
        logger.debug("getForumTopics unavailable; waiting for dynamic discovery")

    return None


def send_private_message(telegram_user_id: int, text: str) -> bool:
    try:
        _api_post(
            "sendMessage",
            data={
                "chat_id": telegram_user_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        return True
    except Exception as exc:
        logger.info("Telegram DM an %s fehlgeschlagen: %s", telegram_user_id, exc)
        return False


def revoke_invite_link(invite_link: str) -> None:
    try:
        _api_post(
            "revokeChatInviteLink",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "invite_link": invite_link,
            },
        )
    except Exception as exc:
        logger.warning("revokeChatInviteLink fehlgeschlagen: %s", exc)


def kick_chat_member(telegram_user_id: int) -> None:
    """Entfernt den User aus der Gruppe, ohne dauerhaften Ban."""
    try:
        _api_post(
            "banChatMember",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "user_id": telegram_user_id,
            },
        )
        _api_post(
            "unbanChatMember",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "user_id": telegram_user_id,
                "only_if_banned": True,
            },
        )
    except Exception as exc:
        logger.warning(
            "Kick von telegram_user_id=%s fehlgeschlagen: %s",
            telegram_user_id,
            exc,
        )


def find_invite_by_telegram_user_id(telegram_user_id: int) -> TelegramInvite | None:
    return (
        TelegramInvite.objects.select_related("user")
        .filter(telegram_user_id=telegram_user_id)
        .first()
    )


def post_or_update_profile_card(profile, invite: TelegramInvite) -> TelegramInvite:
    topic_id = resolve_people_topic_id()
    if topic_id is None:
        raise RuntimeError(
            "Telegram topic «Наши люди» nicht gefunden. "
            "TELEGRAM_PEOPLE_TOPIC_ID setzen oder Topic-Namen beobachten."
        )

    caption = build_profile_caption(profile)
    reply_markup = json.dumps(build_profile_keyboard(profile), ensure_ascii=False)
    photo_bytes, filename = resolve_avatar_bytes(profile)
    chat_id = settings.TELEGRAM_CHAT_ID

    if invite.profile_message_id:
        try:
            media = json.dumps(
                {
                    "type": "photo",
                    "media": "attach://photo",
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                ensure_ascii=False,
            )
            result = _api_post(
                "editMessageMedia",
                data={
                    "chat_id": invite.profile_chat_id or chat_id,
                    "message_id": invite.profile_message_id,
                    "media": media,
                    "reply_markup": reply_markup,
                },
                files={"photo": (filename, photo_bytes)},
            )
            photos = result.get("photo") or []
            if photos:
                invite.profile_photo_file_id = photos[-1].get("file_id", "")
            invite.profile_synced_at = timezone.now()
            invite.save(
                update_fields=[
                    "profile_photo_file_id",
                    "profile_synced_at",
                ]
            )
            return invite
        except Exception as exc:
            logger.warning(
                "editMessageMedia failed for user %s (%s); sending new post",
                invite.user_id,
                exc,
            )

    result = _api_post(
        "sendPhoto",
        data={
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML",
            "message_thread_id": topic_id,
            "reply_markup": reply_markup,
        },
        files={"photo": (filename, photo_bytes)},
    )

    photos = result.get("photo") or []
    invite.profile_message_id = result.get("message_id")
    invite.profile_chat_id = str(result.get("chat", {}).get("id") or chat_id)
    invite.profile_thread_id = topic_id
    invite.profile_photo_file_id = photos[-1].get("file_id", "") if photos else ""
    invite.profile_posted_at = timezone.now()
    invite.profile_synced_at = invite.profile_posted_at
    invite.save(
        update_fields=[
            "profile_message_id",
            "profile_chat_id",
            "profile_thread_id",
            "profile_photo_file_id",
            "profile_posted_at",
            "profile_synced_at",
        ]
    )
    return invite


def process_chat_member_update(chat_member_update: dict) -> bool:
    """
    Markiert Invite als genutzt und triggert Profilpost.
    is_active wird bewusst NICHT mehr gesetzt (E-Mail-Aktivierung).
    Dieselbe Telegram-User-ID darf nur einem Club-Account gehören.
    """
    old_status = chat_member_update.get("old_chat_member", {}).get("status")
    new_member = chat_member_update.get("new_chat_member", {})
    new_status = new_member.get("status")
    invite_link_obj = chat_member_update.get("invite_link")
    user_payload = new_member.get("user") or {}
    telegram_user_id = user_payload.get("id")

    joined = old_status in ("left", "kicked", None) and new_status in (
        "member",
        "administrator",
        "restricted",
    )
    if not (joined and invite_link_obj):
        return False

    invite_url = invite_link_obj.get("invite_link")
    try:
        invite = TelegramInvite.objects.select_related("user").get(
            invite_link=invite_url, used=False
        )
    except TelegramInvite.DoesNotExist:
        return False

    if telegram_user_id:
        existing = find_invite_by_telegram_user_id(int(telegram_user_id))
        if existing and existing.pk != invite.pk:
            logger.warning(
                "Telegram-User %s bereits an Account %s gebunden; "
                "Beitritt für Invite user=%s abgelehnt",
                telegram_user_id,
                existing.user_id,
                invite.user_id,
            )
            if invite.invite_link:
                revoke_invite_link(invite.invite_link)
            kick_chat_member(int(telegram_user_id))
            send_private_message(
                int(telegram_user_id),
                (
                    "Этот Telegram-аккаунт уже привязан к другому профилю клуба. "
                    "Повторная регистрация с тем же Telegram не допускается."
                ),
            )
            return False

    invite.used = True
    invite.used_at = timezone.now()
    if telegram_user_id:
        invite.telegram_user_id = int(telegram_user_id)
    try:
        invite.save(update_fields=["used", "used_at", "telegram_user_id"])
    except IntegrityError:
        logger.warning(
            "Unique telegram_user_id=%s verletzt bei user=%s",
            telegram_user_id,
            invite.user_id,
        )
        if invite.invite_link:
            revoke_invite_link(invite.invite_link)
        if telegram_user_id:
            kick_chat_member(int(telegram_user_id))
        return False

    # --- Lazy import avoids circular imports with Celery tasks.
    from apps.bot.tasks.profile_post import (
        send_profile_completion_reminder,
        sync_telegram_profile_post,
    )

    sync_telegram_profile_post.delay(invite.user_id)
    send_profile_completion_reminder.delay(invite.user_id)
    send_profile_completion_reminder.apply_async(
        args=[invite.user_id], countdown=60 * 60 * 24
    )
    return True


def process_telegram_update(update: dict) -> None:
    if update.get("chat_member"):
        process_chat_member_update(update["chat_member"])
    message = update.get("message") or update.get("channel_post")
    if message:
        process_forum_topic_message(message)
