import logging
from typing import Iterable

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ResendError(RuntimeError):
    """Raised when Resend rejects a message or is unreachable."""

    def __init__(self, message: str, retryable: bool = False):
        """
        retryable distinguishes transient failures (network errors, 5xx)
        worth retrying from permanent ones (4xx, misconfiguration) that
        won't succeed on retry."""
        super().__init__(message)
        self.retryable = retryable


def send_email(
    subject: str,
    message: str,
    html_message: str,
    to: str | Iterable[str],
    reply_to: str | None = None,
) -> str:
    """
    Send a transactional email via the Resend API.

    Args:
        subject: Email subject line.
        message: Plain-text body.
        html_message: HTML body.
        to: A single recipient address or an iterable of addresses.
        reply_to: Optional Reply-To address.

    Returns:
        The Resend message id, or "" if the response body wasn't parseable
        JSON.

    Raises:
        ResendError: If the request could not be sent or Resend rejected it.
    """
    api_key = settings.RESEND_API_KEY
    from_email = settings.RESEND_FROM_EMAIL
    endpoint = settings.RESEND_ENDPOINT
    if not api_key:
        raise ResendError("RESEND_API_KEY is not configured")
    if not from_email:
        raise ResendError("RESEND_FROM_EMAIL is not configured")

    recipients = [to] if isinstance(to, str) else list(to)

    payload: dict = {
        "from": from_email,
        "to": recipients,
        "subject": subject,
        "text": message,
        "html": html_message,
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
            timeout=settings.RESEND_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ResendError(f"Resend request failed: {exc}", retryable=True) from exc

    if response.status_code >= 400:
        detail = response.text[:500]
        logger.error(f"Resend rejected message {response.status_code}, {detail}")
        raise ResendError(
            f"Resend returned HTTP {response.status_code}: {detail}",
            retryable=response.status_code >= 500,
        )

    try:
        return response.json().get("id", "")
    except ValueError:
        logger.warning(f"Resend returned non-JSON response: {response.text[:200]}")
        return ""
