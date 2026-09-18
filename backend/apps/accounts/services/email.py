import logging
from typing import Iterable

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ResendError(RuntimeError):
    """Raised when Resend rejects a message or is unreachable."""

    ...


def send_email(
    subject: str,
    message,
    html_message: str,
    to: str,
    reply_to: str | None = None,
) -> str:

    api_key = getattr(settings, "RESEND_API_KEY", "") or ""
    from_email = getattr(settings, "RESEND_FROM_EMAIL", "") or ""
    endpoint = (
        getattr(settings, "RESEND_ENDPOINT", "") or "https://api.resend.com/emails"
    )
    if not api_key:
        raise ResendError("RESEND_API_KEY is not configured")
    if not from_email:
        raise ResendError("RESEND_FROM_EMAIL is not configured")

    payload: dict = {
        "from": from_email,
        "to": to,
        "subject": subject,
        "message": message,
        "html_message": html_message,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=getattr(settings, "RESEND_TIMEOUT", 15),
        )
    except requests.RequestException as exc:
        raise ResendError(f"Resend request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:500]
        logger.error(f"Resend rejected message {response.status_code}, {detail}")
        raise ResendError(f"Resend returned HTTP {response.status_code}: {detail}")

    try:
        return response.json().get("id", "")
    except ValueError:
        return ""
