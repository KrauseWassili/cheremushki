import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from apps.accounts.services.email import ResendError, send_email
from apps.accounts.tokens import email_change_token_generator
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import CustomUser

logger = logging.getLogger(__name__)


def _build_frontend_url(path: str) -> str:
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{frontend_url}{path}"


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_activation_email(self, user_id: int):
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    if user.is_active:
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_url = _build_frontend_url(f"/activate?uid={uid}&token={token}")

    subject = "Активируй аккаунт"
    message = (
        f"Здравствуй, {user.first_name}!\n\n"
        "Чтобы активировать аккаунт, перейди по ссылке:\n"
        f"{activation_url}\n"
    )
    html_message = render_to_string(
        "emails/account_activation.html",
        {"user": user, "activation_url": activation_url},
    )

    try:
        send_email(
            subject=subject,
            message=message,
            html_message=html_message,
            to=user.email,
        )
    except ResendError as exc:
        if exc.retryable:
            raise self.retry(exc=exc)
        logger.error(f"Permanent failure sending activation email for user_id={user_id}: {exc}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_email_change_confirmation(self, user_id: int):
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    if not user.pending_email:
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_change_token_generator.make_token(user)
    confirm_url = _build_frontend_url(f"/email-change/confirm?uid={uid}&token={token}")

    html_message = render_to_string(
        "emails/email_change.html",
        {"user": user, "confirm_url": confirm_url, "new_email": user.pending_email},
    )

    subject = "Подтверди новую почту"
    message = (
        f"Здравствуй, {user.first_name}!\n\n"
        "Чтобы подтвердить изменение email, перейди по ссылке:\n"
        f"{confirm_url}\n"
    )
    try:
        send_email(
            subject=subject,
            message=message,
            html_message=html_message,
            to=user.pending_email,
        )
    except ResendError as exc:
        if exc.retryable:
            raise self.retry(exc=exc)
        logger.error(f"Permanent failure sending email change confirmation for user_id={user_id}: {exc}")
        raise
