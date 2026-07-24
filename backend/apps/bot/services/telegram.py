import requests
from django.conf import settings
from django.utils import timezone

from ..models import TelegramInvite

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


def create_single_use_invite_link(name: str) -> str:
    response = requests.post(
        f"{TELEGRAM_API_BASE}/createChatInviteLink",
        data={"chat_id": settings.TELEGRAM_CHAT_ID, "name": name, "member_limit": 1},
        timeout=10,
    )
    data = response.json() if response.content else {}
    if not response.ok or not data.get("ok"):
        raise RuntimeError(
            "Telegram createChatInviteLink fehlgeschlagen "
            f"(HTTP {response.status_code}): {data.get('description') or response.text}"
        )
    return data["result"]["invite_link"]


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    params = {"timeout": timeout, "allowed_updates": ["chat_member"]}
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


def process_chat_member_update(chat_member_update: dict) -> bool:
    """
    Gemeinsame Logik für Webhook UND Polling.
    Gibt True zurück, wenn ein User aktiviert wurde.
    """
    old_status = chat_member_update.get("old_chat_member", {}).get("status")
    new_member = chat_member_update.get("new_chat_member", {})
    new_status = new_member.get("status")
    invite_link_obj = chat_member_update.get("invite_link")

    joined = old_status in ("left", "kicked", None) and new_status == "member"
    if not (joined and invite_link_obj):
        return False

    invite_url = invite_link_obj.get("invite_link")
    try:
        invite = TelegramInvite.objects.select_related("user").get(
            invite_link=invite_url, used=False
        )
    except TelegramInvite.DoesNotExist:
        return False

    invite.used = True
    invite.used_at = timezone.now()
    invite.save(update_fields=["used", "used_at"])

    invite.user.is_active = True
    invite.user.save(update_fields=["is_active"])

    return True