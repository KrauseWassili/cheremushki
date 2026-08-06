from __future__ import annotations

import html
import io
import re
from typing import TYPE_CHECKING

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from apps.profiles.models import MemberProfile

PLACEHOLDER_BIO = "Профиль ещё заполняется"
PLACEHOLDER_HELP = "Скоро расскажу, чем могу помочь"
PLACEHOLDER_LOOKING = "Скоро расскажу, что сейчас интересно"
TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")

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
    return caption[:1024]

#Нормализуем имя пользователя тг для кнопки под постом
def normalize_telegram_username(value: str | None) -> str | None:
    username = (value or "").strip()

    # Разрешаем хранить как @username
    username = username.removeprefix("@")

    # Или как https://t.me/username
    if username.startswith("https://t.me/"):
        username = username.removeprefix("https://t.me/")
        username = username.split("?", maxsplit=1)[0]
        username = username.strip("/")

    if not TELEGRAM_USERNAME_RE.fullmatch(username):
        return None

    return username


def build_profile_keyboard(profile: MemberProfile) -> dict:
    keyboard = [
        [
            {
                "text": "Открыть профиль в клубе",
                "url": build_profile_url(profile),
            }
        ]
    ]

    #добавлена кнопка личного сообщения пользователя. 
    telegram_username = normalize_telegram_username(
        profile.telegram_username
    )
    #появляется, если пользователь в профиле выбрал прямой способ контакта и указал имя пользователя тг
    if profile.contact_mode == "direct" and telegram_username:
        keyboard.append(
            [
                {
                    "text": "Написать сообщение",
                    "url": f"https://t.me/{telegram_username}",
                }
            ]
        )

    return {"inline_keyboard": keyboard}


def generate_placeholder_avatar(profile: MemberProfile) -> bytes:
    initials_source = f"{profile.user.first_name[:1]}{profile.user.last_name[:1]}"
    initials = (initials_source or "?").upper()

    size = 512
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
    if profile.avatar:
        try:
            profile.avatar.open("rb")
            data = profile.avatar.read()
            profile.avatar.close()
            name = profile.avatar.name.rsplit("/", 1)[-1] or "avatar.jpg"
            return data, name
        except Exception:
            pass
    return generate_placeholder_avatar(profile), "avatar.png"
