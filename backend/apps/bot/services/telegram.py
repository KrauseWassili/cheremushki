"""Anbindung an die Telegram-Bot-API.

Zwei Grundsätze, die den Aufbau dieser Datei erklären:

1. **Der Bot-Token darf nirgends in einem Log landen.** Er steckt in jeder
   Request-URL, und ``requests``-Exceptions tragen die URL in ihrer Message.
   Deshalb gibt es genau eine Stelle (:func:`_api_call`), die HTTP spricht, und
   sie übersetzt Transportfehler in :class:`TelegramTransportError` – ohne URL
   und ohne ``__cause__``.
2. **Ein neuer Post im Kanal ist nicht zurücknehmbar, ein Retry schon.** Der
   Fallback von "bearbeiten" auf "neu senden" greift nur, wenn die alte
   Nachricht nachweislich verloren ist. Alles andere wird weitergereicht,
   damit der Celery-Retry greift.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone

from ..exceptions import (
    TelegramAPIError,
    TelegramConfigurationError,
    TelegramTransportError,
)
from ..models import TelegramForumTopic, TelegramInvite
from .profile_card import (
    build_profile_caption,
    build_profile_keyboard,
    resolve_avatar_bytes,
)

if TYPE_CHECKING:
    from apps.profiles.models import MemberProfile

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

API_TIMEOUT_SECONDS = 30
LONG_POLL_MARGIN_SECONDS = 10
TOPIC_DISCOVERY_TIMEOUT_SECONDS = 15
TOPIC_DISCOVERY_LIMIT = 100

PEOPLE_TOPIC_CACHE_KEY = "telegram_people_topic_id"
PEOPLE_TOPIC_CACHE_TTL_SECONDS = 60 * 60


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def _api_call(
    method: str,
    *,
    data: dict | None = None,
    files: dict | None = None,
    timeout: int = API_TIMEOUT_SECONDS,
) -> Any:
    """Einzige Ein- und Ausgangstür zur Bot-API.

    Telegram akzeptiert für alle Methoden POST, deshalb gibt es hier keinen
    zweiten Codepfad für GET.

    Raises:
        TelegramTransportError: Netzwerkfehler oder unlesbare Antwort.
        TelegramAPIError: Telegram hat mit ``ok: false`` geantwortet.
    """
    try:
        response = requests.post(
            f"{TELEGRAM_API_BASE}/{method}",
            data=data or {},
            files=files,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        # Bewusst kein 'from exc' und kein str(exc): beide enthalten die URL
        # und damit den Bot-Token. Diese Exception wird geloggt.
        raise TelegramTransportError(
            f"Telegram {method}: {type(exc).__name__}"
        ) from None

    try:
        payload = response.json() if response.content else {}
    except ValueError:
        raise TelegramTransportError(
            f"Telegram {method}: Antwort ist kein JSON (HTTP {response.status_code})"
        ) from None

    if not response.ok or not payload.get("ok"):
        raise TelegramAPIError(method, response.status_code, payload)
    return payload["result"]


# --------------------------------------------------------------------------- #
# Invites, Nachrichten, Mitgliedschaft
# --------------------------------------------------------------------------- #


def create_single_use_invite_link(name: str) -> str:
    result = _api_call(
        "createChatInviteLink",
        data={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "name": name,
            "member_limit": 1,
        },
    )
    return result["invite_link"]


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    data: dict[str, Any] = {
        "timeout": timeout,
        "allowed_updates": json.dumps(
            ["chat_member", "message", "channel_post", "my_chat_member"]
        ),
    }
    if offset is not None:
        data["offset"] = offset

    return _api_call(
        "getUpdates", data=data, timeout=timeout + LONG_POLL_MARGIN_SECONDS
    )


def send_private_message(telegram_user_id: int, text: str) -> bool:
    """Best effort – eine nicht zustellbare DM darf nichts blockieren."""
    try:
        _api_call(
            "sendMessage",
            data={
                "chat_id": telegram_user_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        return True
    except (TelegramAPIError, TelegramTransportError) as exc:
        logger.info("Telegram DM an %s fehlgeschlagen: %s", telegram_user_id, exc)
        return False


def revoke_invite_link(invite_link: str) -> None:
    try:
        _api_call(
            "revokeChatInviteLink",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "invite_link": invite_link,
            },
        )
    except (TelegramAPIError, TelegramTransportError) as exc:
        logger.warning("revokeChatInviteLink fehlgeschlagen: %s", exc)


def kick_chat_member(telegram_user_id: int) -> None:
    """Entfernt den User aus der Gruppe, ohne dauerhaften Ban."""
    try:
        _api_call(
            "banChatMember",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "user_id": telegram_user_id,
            },
        )
        _api_call(
            "unbanChatMember",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "user_id": telegram_user_id,
                "only_if_banned": True,
            },
        )
    except (TelegramAPIError, TelegramTransportError) as exc:
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


# --------------------------------------------------------------------------- #
# Forum-Topics
# --------------------------------------------------------------------------- #


def _people_topic_name() -> str:
    return str(
        getattr(settings, "TELEGRAM_PEOPLE_TOPIC_NAME", "Наши люди") or ""
    ).strip()


def remember_forum_topic(name: str, thread_id: int) -> None:
    """Persistiert eine entdeckte Topic-Zuordnung.

    Die Entdeckung passiert im Web-Prozess, gebraucht wird sie im
    Celery-Worker – deshalb DB statt Cache. Der Cache davor ist nur ein
    Beschleuniger für den heißen Pfad.
    """
    name = (name or "").strip()
    if not name:
        return

    TelegramForumTopic.objects.update_or_create(
        name=name, defaults={"thread_id": int(thread_id)}
    )

    if name.lower() == _people_topic_name().lower():
        cache.set(
            PEOPLE_TOPIC_CACHE_KEY, int(thread_id), PEOPLE_TOPIC_CACHE_TTL_SECONDS
        )
        logger.info("Telegram people topic aufgelöst: %s", thread_id)


def process_forum_topic_message(message: dict) -> None:
    """Entdeckt Topic-IDs aus Service-Nachrichten der Gruppe."""
    created = message.get("forum_topic_created")
    edited = message.get("forum_topic_edited")
    thread_id = message.get("message_thread_id")
    if not thread_id:
        return

    if created and created.get("name"):
        remember_forum_topic(created["name"], thread_id)
    elif edited and edited.get("name"):
        remember_forum_topic(edited["name"], thread_id)


def parse_people_topic_id(raw: str | int | None) -> int | None:
    """Akzeptiert reine Thread-IDs ('3') und t.me/c-Formate ('4378956431/3')."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    try:
        return int(value)
    except ValueError:
        logger.warning("Ungültige TELEGRAM_PEOPLE_TOPIC_ID: %r", raw)
        return None


def resolve_people_topic_id() -> int | None:
    """Ermittelt die Thread-ID des Topics «Наши люди».

    Reihenfolge: Cache → Konfiguration → DB → einmalige Abfrage bei Telegram.
    """
    cached = cache.get(PEOPLE_TOPIC_CACHE_KEY)
    if cached is not None:
        return int(cached)

    configured = parse_people_topic_id(
        getattr(settings, "TELEGRAM_PEOPLE_TOPIC_ID", "") or ""
    )
    if configured is not None:
        cache.set(PEOPLE_TOPIC_CACHE_KEY, configured, PEOPLE_TOPIC_CACHE_TTL_SECONDS)
        return configured

    expected = _people_topic_name()
    stored = TelegramForumTopic.objects.filter(name__iexact=expected).first()
    if stored is not None:
        cache.set(
            PEOPLE_TOPIC_CACHE_KEY, stored.thread_id, PEOPLE_TOPIC_CACHE_TTL_SECONDS
        )
        return stored.thread_id

    return _discover_people_topic_id(expected)


def _discover_people_topic_id(expected: str) -> int | None:
    """Fragt die Topic-Liste ab. Der Endpoint ist nicht überall verfügbar."""
    try:
        topics = _api_call(
            "getForumTopics",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "limit": TOPIC_DISCOVERY_LIMIT,
            },
            timeout=TOPIC_DISCOVERY_TIMEOUT_SECONDS,
        )
    except (TelegramAPIError, TelegramTransportError) as exc:
        logger.info(
            "getForumTopics nicht verfügbar (%s) – warte auf dynamische "
            "Entdeckung über Service-Nachrichten",
            exc,
        )
        return None

    if isinstance(topics, dict):
        topics = topics.get("topics") or []

    found: int | None = None
    for topic in topics:
        name = topic.get("name") or ""
        thread_id = topic.get("message_thread_id") or topic.get("message_id")
        if not thread_id:
            continue
        remember_forum_topic(name, int(thread_id))
        if name.strip().lower() == expected.lower():
            found = int(thread_id)
    return found


# --------------------------------------------------------------------------- #
# Profilkarte
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProfileCardPayload:
    """Alles, was einen Profilpost inhaltlich ausmacht."""

    caption: str
    reply_markup: str
    photo_bytes: bytes
    filename: str

    @property
    def digest(self) -> str:
        """Fingerabdruck des Postinhalts.

        Stimmt er mit dem gespeicherten überein, entfällt der Telegram-Call –
        die billigste Antwort ist die, die man gar nicht erst erfragt.
        """
        checksum = hashlib.sha256()
        checksum.update(self.caption.encode())
        checksum.update(self.reply_markup.encode())
        checksum.update(self.photo_bytes)
        return checksum.hexdigest()


def build_profile_card_payload(profile: MemberProfile) -> ProfileCardPayload:
    photo_bytes, filename = resolve_avatar_bytes(profile)
    return ProfileCardPayload(
        caption=build_profile_caption(profile),
        reply_markup=json.dumps(build_profile_keyboard(profile), ensure_ascii=False),
        photo_bytes=photo_bytes,
        filename=filename,
    )


def post_or_update_profile_card(
    profile: MemberProfile, invite: TelegramInvite
) -> TelegramInvite:
    """Postet die Profilkarte oder aktualisiert den bestehenden Post.

    Ein neuer Post entsteht nur, wenn es noch keinen gibt oder der bestehende
    nachweislich nicht mehr bearbeitbar ist. Jeder andere Fehler wird
    weitergereicht, damit der Celery-Retry greift: Ein Duplikat im Kanal ist
    für alle sichtbar und nicht zurücknehmbar, ein Retry kostet nichts.
    """
    topic_id = resolve_people_topic_id()
    if topic_id is None:
        raise TelegramConfigurationError(
            "Telegram topic «Наши люди» nicht gefunden. "
            "TELEGRAM_PEOPLE_TOPIC_ID setzen oder Topic-Namen beobachten."
        )

    payload = build_profile_card_payload(profile)

    if invite.profile_message_id:
        if invite.profile_content_hash == payload.digest:
            logger.debug(
                "Profilpost user=%s unverändert – kein Telegram-Call",
                invite.user_id,
            )
            return _touch_synced_at(invite)

        try:
            result = _edit_profile_card(invite, payload)
        except TelegramAPIError as exc:
            if exc.is_not_modified:
                logger.info("Profilpost user=%s war bereits aktuell", invite.user_id)
                return _touch_synced_at(invite, digest=payload.digest)
            if not exc.is_message_gone:
                raise
            logger.warning(
                "Profilpost user=%s nicht mehr editierbar (%s) – wird neu gesendet",
                invite.user_id,
                exc.description,
            )
        else:
            # DB-Schreibzugriff bewusst außerhalb des try: Ein Fehler hier darf
            # nicht als Telegram-Fehler behandelt werden und einen zweiten Post
            # auslösen, obwohl der Edit erfolgreich war.
            return _save_edit_result(invite, result, payload.digest)

    return _send_new_profile_card(invite, payload, topic_id)


def _edit_profile_card(invite: TelegramInvite, payload: ProfileCardPayload) -> Any:
    media = json.dumps(
        {
            "type": "photo",
            "media": "attach://photo",
            "caption": payload.caption,
            "parse_mode": "HTML",
        },
        ensure_ascii=False,
    )
    return _api_call(
        "editMessageMedia",
        data={
            "chat_id": invite.profile_chat_id or settings.TELEGRAM_CHAT_ID,
            "message_id": invite.profile_message_id,
            "media": media,
            "reply_markup": payload.reply_markup,
        },
        files={"photo": (payload.filename, payload.photo_bytes)},
    )


def _send_new_profile_card(
    invite: TelegramInvite, payload: ProfileCardPayload, topic_id: int
) -> TelegramInvite:
    result = _api_call(
        "sendPhoto",
        data={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "caption": payload.caption,
            "parse_mode": "HTML",
            "message_thread_id": topic_id,
            "reply_markup": payload.reply_markup,
        },
        files={"photo": (payload.filename, payload.photo_bytes)},
    )
    return _save_send_result(invite, result, topic_id, payload.digest)


def _largest_photo_file_id(result: Any) -> str:
    """``editMessageMedia`` liefert bei Inline-Nachrichten ``True`` statt Message."""
    if not isinstance(result, dict):
        return ""
    photos = result.get("photo") or []
    return photos[-1].get("file_id", "") if photos else ""


def _touch_synced_at(
    invite: TelegramInvite, digest: str | None = None
) -> TelegramInvite:
    invite.profile_synced_at = timezone.now()
    fields = ["profile_synced_at"]
    if digest is not None:
        invite.profile_content_hash = digest
        fields.append("profile_content_hash")
    invite.save(update_fields=fields)
    return invite


def _save_edit_result(
    invite: TelegramInvite, result: Any, digest: str
) -> TelegramInvite:
    file_id = _largest_photo_file_id(result)
    if file_id:
        invite.profile_photo_file_id = file_id
    invite.profile_content_hash = digest
    invite.profile_synced_at = timezone.now()
    invite.save(
        update_fields=[
            "profile_photo_file_id",
            "profile_content_hash",
            "profile_synced_at",
        ]
    )
    return invite


def _save_send_result(
    invite: TelegramInvite, result: Any, topic_id: int, digest: str
) -> TelegramInvite:
    invite.profile_message_id = result.get("message_id")
    invite.profile_chat_id = str(
        result.get("chat", {}).get("id") or settings.TELEGRAM_CHAT_ID
    )
    invite.profile_thread_id = topic_id
    invite.profile_photo_file_id = _largest_photo_file_id(result)
    invite.profile_content_hash = digest
    invite.profile_posted_at = timezone.now()
    invite.profile_synced_at = invite.profile_posted_at
    invite.save(
        update_fields=[
            "profile_message_id",
            "profile_chat_id",
            "profile_thread_id",
            "profile_photo_file_id",
            "profile_content_hash",
            "profile_posted_at",
            "profile_synced_at",
        ]
    )
    return invite


# --------------------------------------------------------------------------- #
# Updates
# --------------------------------------------------------------------------- #


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

    if telegram_user_id and _reject_duplicate_account(invite, int(telegram_user_id)):
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

    _schedule_post_join_tasks(invite.user_id)
    return True


def _reject_duplicate_account(invite: TelegramInvite, telegram_user_id: int) -> bool:
    """
    Prüft, ob dieser Telegram-Account schon an einen anderen Club-Account geht.
    """
    existing = find_invite_by_telegram_user_id(telegram_user_id)
    if not existing or existing.pk == invite.pk:
        return False

    logger.warning(
        "Telegram-User %s bereits an Account %s gebunden; "
        "Beitritt für Invite user=%s abgelehnt",
        telegram_user_id,
        existing.user_id,
        invite.user_id,
    )
    if invite.invite_link:
        revoke_invite_link(invite.invite_link)
    kick_chat_member(telegram_user_id)
    send_private_message(
        telegram_user_id,
        (
            "Этот Telegram-аккаунт уже привязан к другому профилю клуба. "
            "Повторная регистрация с тем же Telegram не допускается."
        ),
    )
    return True


def _schedule_post_join_tasks(user_id: int) -> None:
    # Lazy import: Die Tasks importieren diesen Service.
    from apps.bot.tasks.profile_post import (
        PROFILE_REMINDER_DELAY_SECONDS,
        send_profile_completion_reminder,
        sync_telegram_profile_post,
    )

    sync_telegram_profile_post.delay(user_id)

    # Bewusst zwei Reminder: einer sofort beim Beitritt, einer nach 24 h. Der
    # Task bricht ab, sobald das Profil vollständig ist, und zählt maximal zwei
    # Versendungen. Falls die Sofort-Mail unerwünscht ist, ist hier die Stelle.
    send_profile_completion_reminder.delay(user_id)
    send_profile_completion_reminder.apply_async(
        args=[user_id], countdown=PROFILE_REMINDER_DELAY_SECONDS
    )


def process_telegram_update(update: dict) -> None:
    if update.get("chat_member"):
        process_chat_member_update(update["chat_member"])
    message = update.get("message") or update.get("channel_post")
    if message:
        process_forum_topic_message(message)
