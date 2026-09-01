from __future__ import annotations

import html
import io
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

from apps.profiles.models import ContactMode
from apps.profiles.telegram import build_telegram_dm_url, normalize_telegram_username

if TYPE_CHECKING:
    from apps.profiles.models import MemberProfile

logger = logging.getLogger(__name__)

PLACEHOLDER_BIO = "Профиль ещё заполняется"
PLACEHOLDER_HELP = "Скоро расскажу, чем могу помочь"
PLACEHOLDER_LOOKING = "Скоро расскажу, что сейчас интересно"

CAPTION_MAX_LENGTH = 1024
AVATAR_SIZE = 512


def _esc(value: str) -> str:
    return html.escape((value or "").strip())


def resolve_profile_link_base() -> str:
    """
    Telegram akzeptiert in URL-Buttons nur https.
    Bei lokalem FRONTEND_URL (http/localhost) → Mock-Base für die Entwicklung.
    """
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    if frontend.startswith("https://"):
        return frontend
    mock = getattr(settings, "TELEGRAM_PROFILE_URL_BASE", "https://example.com")
    return str(mock).rstrip("/")


def resolve_direct_telegram_username(profile: MemberProfile) -> str | None:
    """
    Liefert den Telegram Handle nur bei ContactMode.DIRECT.

    Der Post ist für die ganze Gruppe sichtbar, der Handle würde also allen
    Mitgliedern offen liegen. Nur dieser Kontaktmodus erlaubt das ausdrücklich.
    """
    if profile.contact_mode != ContactMode.DIRECT:
        return None

    if not profile.telegram_username:
        return None
    return normalize_telegram_username(profile.telegram_username)


def _truncate_at_line(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    newline = cut.rfind("\n")
    if newline != -1:
        return cut[:newline]
    return cut


def _fit_caption(body: str, footer: str = "") -> str:
    if not footer:
        return _truncate_at_line(body, CAPTION_MAX_LENGTH)
    if len(footer) > CAPTION_MAX_LENGTH:
        return _truncate_at_line(body, CAPTION_MAX_LENGTH)
    body = _truncate_at_line(body, CAPTION_MAX_LENGTH - len(footer))
    return body + footer


def build_profile_url(profile: MemberProfile) -> str:
    slug = profile.slug or f"member-{profile.user_id}"
    return f"{resolve_profile_link_base()}/members/{slug}"


def build_profile_caption(profile: MemberProfile) -> str:
    user = profile.user
    name = _esc(user.full_name) or _esc(user.email)
    headline = (profile.headline or "Участник").strip()
    city = (profile.city or "—").strip()
    subtitle = _esc(f"{headline} · {city}")

    bio = _esc(profile.bio) or PLACEHOLDER_BIO
    can_help = _esc(profile.can_help_with) or PLACEHOLDER_HELP
    looking_for = _esc(profile.looking_for) or PLACEHOLDER_LOOKING

    tags = [str(tag).strip() for tag in (profile.tags or []) if str(tag).strip()]
    tags_line = _esc(" · ".join(tags)) if tags else "—"

    caption = (
        f"<b>{name}</b>\n"
        f"<i>{subtitle}</i>\n"
        f"\n"
        f"{bio}\n"
        f"\n"
        f"<b>Могу помочь</b>\n"
        f"{can_help}\n"
        f"\n"
        f"<b>Сейчас интересно</b>\n"
        f"{looking_for}\n"
        f"\n"
        f"<b>Теги</b>\n"
        f"{tags_line}"
    )
    username = resolve_direct_telegram_username(profile)
    footer = ""
    if username:
        footer = (
            f"\n\n<b>Telegram</b>\n"
            f'<a href="{build_telegram_dm_url(username)}">@{username}</a>'
        )
    return _fit_caption(caption, footer)


def build_profile_keyboard(profile: MemberProfile) -> dict:
    """
    Baut das Inline-Keyboard unter dem Profilpost.
    DM-Button nur, wenn resolve_direct_telegram_username einen Handle liefert.
    """
    keyboard = [
        [
            {
                "text": "Открыть профиль в клубе",
                "url": build_profile_url(profile),
            }
        ]
    ]

    username = resolve_direct_telegram_username(profile)

    if username:
        keyboard.append(
            [
                {
                    "text": "Написать сообщение",
                    "url": build_telegram_dm_url(username),
                }
            ]
        )
    elif profile.contact_mode == ContactMode.DIRECT and profile.telegram_username:
        logger.warning(
            "Profil user=%s: telegram_username %r nicht verwertbar – DM-Button entfällt",
            profile.user_id,
            profile.telegram_username,
        )

    return {"inline_keyboard": keyboard}


def generate_placeholder_avatar(profile: MemberProfile) -> bytes:
    initials_source = f"{profile.user.first_name[:1]}{profile.user.last_name[:1]}"
    initials = (initials_source or "?").upper()

    size = AVATAR_SIZE
    image = Image.new("RGB", (size, size), color=(36, 48, 66))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 180)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    position = ((size - text_w) / 2, (size - text_h) / 2 - 10)
    draw.text(position, initials, fill=(236, 240, 245), font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def resolve_avatar_bytes(profile: MemberProfile) -> tuple[bytes, str]:
    """
    Liest den Avatar fällt auf ein generiertes Initialen Bild zurück.
    """
    if profile.avatar:
        try:
            profile.avatar.open("rb")
            data = profile.avatar.read()
            profile.avatar.close()
            name = profile.avatar.name.rsplit("/", 1)[-1] or "avatar.jpg"
            return data, name
        except (OSError, ValueError) as exc:  # ValueError: SuspiciousFileOperation
            # Storage nicht erreichbar oder Datei weg: Der Post soll trotzdem
            # rausgehen, aber der Fehlschlag darf nicht unsichtbar bleiben –
            # er ändert den Bildinhalt und damit den Post.
            logger.warning(
                "Avatar für user=%s nicht lesbar (%s) – Platzhalter wird genutzt",
                profile.user_id,
                exc,
            )
    return generate_placeholder_avatar(profile), "avatar.png"
