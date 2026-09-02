from celery import shared_task
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator

from apps.accounts.tokens import email_change_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import CustomUser


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
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip(
        "/"
    )
    activation_url = f"{frontend_url}/activate?uid={uid}&token={token}"

    try:
        html_message = render_to_string(
            "emails/account_activation.html",
            {"user": user, "activation_url": activation_url},
        )
        send_mail(
            subject="Активируй аккаунт",
            message=(
                f"Здравствуй, {user.first_name}!\n\n"
                "Чтобы активировать аккаунт, перейди по ссылке:\n"
                f"{activation_url}\n"
            ),
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception as exc:
        raise self.retry(exc=exc)


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
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip(
        "/"
    )
    confirm_url = f"{frontend_url}/email-change/confirm?uid={uid}&token={token}"

    html_message = render_to_string(
        "emails/email_change.html",
        {"user": user, "confirm_url": confirm_url, "new_email": user.pending_email},
    )
    send_mail(
        subject="Подтверди новую почту",
        message=(
            f"Здравствуй, {user.first_name}!\n\n"
            "Чтобы подтвердить изменение email, перейди по ссылке:\n"
            f"{confirm_url}\n"
        ),
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.pending_email],
    )
