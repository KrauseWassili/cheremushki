import logging
from typing import Iterable

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

# 429 ist ein 4xx, aber kein dauerhafter Fehler: Resend drosselt nur (Rate
# Limit pro Sekunde), derselbe Request geht kurz darauf durch. Ohne Retry
# ginge z. B. eine Einladung verloren, nur weil zwei Mails gleichzeitig raus
# wollten.
_RETRYABLE_CLIENT_STATUSES = frozenset({429})
_SERVER_ERROR_STATUS = 500


class ResendError(RuntimeError):
    """Resend hat die Mail abgelehnt oder war nicht erreichbar."""

    def __init__(self, message: str, retryable: bool = False):
        """
        retryable trennt vorübergehende Fehler (Netzwerk, 5xx, 429), bei denen
        ein Retry lohnt, von dauerhaften (übrige 4xx, Fehlkonfiguration), die
        auch beim nächsten Versuch scheitern."""
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
    Verschickt eine Transaktionsmail über die Resend-API.

    Args:
        subject: Betreff.
        message: Textfassung.
        html_message: HTML-Fassung.
        to: Eine Empfängeradresse oder mehrere.
        reply_to: Optionale Reply-To-Adresse.

    Returns:
        Die Resend-Message-ID, oder "", wenn die Antwort kein JSON war oder
        die Mail über den lokalen SMTP-Ersatzweg ging.

    Raises:
        ResendError: Request nicht absetzbar oder von Resend abgelehnt.
    """
    api_key = settings.RESEND_API_KEY
    from_email = settings.RESEND_FROM_EMAIL
    endpoint = settings.RESEND_ENDPOINT
    recipients = [to] if isinstance(to, str) else list(to)
    if not api_key and settings.DEBUG:
        return _send_via_local_smtp(
            subject=subject,
            message=message,
            html_message=html_message,
            recipients=recipients,
            reply_to=reply_to,
        )
    if not api_key:
        raise ResendError("RESEND_API_KEY is not configured")
    if not from_email:
        raise ResendError("RESEND_FROM_EMAIL is not configured")

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
        logger.error(
            "Resend hat die Mail abgelehnt: HTTP %s, %s", response.status_code, detail
        )
        raise ResendError(
            f"Resend returned HTTP {response.status_code}: {detail}",
            retryable=_is_retryable_status(response.status_code),
        )

    try:
        return response.json().get("id", "")
    except ValueError:
        logger.warning("Resend-Antwort ist kein JSON: %s", response.text[:200])
        return ""


def _is_retryable_status(status_code: int) -> bool:
    return (
        status_code >= _SERVER_ERROR_STATUS or status_code in _RETRYABLE_CLIENT_STATUSES
    )


def _send_via_local_smtp(
    *,
    subject: str,
    message: str,
    html_message: str,
    recipients: list[str],
    reply_to: str | None,
) -> str:
    """
    Lokaler Ersatzweg ohne Resend-Key: zustellen über Djangos E-Mail-Backend
    (per Default SMTP an mailcatcher, EMAIL_HOST/EMAIL_PORT aus settings.py).

    Nur bei DEBUG=True erreichbar – in Produktion soll ein fehlender Key laut
    scheitern (und check --deploy ihn melden), statt Mails an einen nicht
    existierenden SMTP-Server zu schicken. Fehler werden als ResendError
    gemeldet, damit die Aufrufer ihre Retry-Logik nicht doppelt brauchen;
    ein nicht laufender mailcatcher ist vorübergehend, daher retryable.
    """
    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=settings.RESEND_FROM_EMAIL or settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        reply_to=[reply_to] if reply_to else None,
    )
    email.attach_alternative(html_message, "text/html")
    try:
        email.send()
    except OSError as exc:  # smtplib.SMTPException erbt von OSError
        raise ResendError(f"Local SMTP delivery failed: {exc}", retryable=True) from exc
    return ""
