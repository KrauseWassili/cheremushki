"""
E-Mail Wechsel: Anfrage hinterlegen und nach Token Bestätigung anwenden.
"""

from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from apps.accounts.models import CustomUser
from apps.accounts.tokens import email_change_token_generator


class EmailChangeError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def request_email_change(user: CustomUser, new_email: str) -> None:
    user.pending_email = new_email
    user.save(update_fields=["pending_email"])


def confirm_email_change(uid_b64: str, token: str) -> CustomUser:
    uid = _decode_uid(uid_b64)
    with transaction.atomic():
        try:
            user = CustomUser.objects.select_for_update().get(pk=uid)
        except CustomUser.DoesNotExist as exc:
            raise EmailChangeError("invalid_link") from exc
        if not user.pending_email:
            raise EmailChangeError("nothing_pending")
        if not email_change_token_generator.check_token(user, token):
            raise EmailChangeError("invalid_token")
        if _is_email_taken(user.pending_email, exclude_pk=user.pk):
            raise EmailChangeError("taken")
        user.email = user.pending_email
        user.pending_email = ""
        user.save(update_fields=["email", "pending_email"])
    return user


def _decode_uid(uid_b64: str) -> str:
    try:
        return force_str(urlsafe_base64_decode(uid_b64))
    except (ValueError, TypeError, OverflowError) as exc:
        raise EmailChangeError("invalid_link") from exc


def _is_email_taken(email: str, *, exclude_pk: int) -> bool:
    return (
        CustomUser.objects.filter(email__iexact=email).exclude(pk=exclude_pk).exists()
    )
