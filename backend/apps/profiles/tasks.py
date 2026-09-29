import logging

from celery import shared_task
from django.template.loader import render_to_string

from apps.accounts.services.email import ResendError, send_email

from .models import ContactRequest, ContactRequestStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_contact_request_email(self, contact_request_id: int):
    try:
        contact = ContactRequest.objects.select_related(
            "from_user", "to_profile__user"
        ).get(pk=contact_request_id)
    except ContactRequest.DoesNotExist:
        return

    to_user = contact.to_profile.user
    from_user = contact.from_user

    html_message = render_to_string(
        "emails/contact_request.html",
        {
            "from_user": from_user,
            "to_user": to_user,
            "message": contact.message,
        },
    )

    # Das try umschließt nur den Netzwerkaufruf – der Statuswechsel gehört in
    # die Zweige, damit er den Ausgang des Versands beschreibt und nicht den
    # eines danebenliegenden Fehlers.
    try:
        send_email(
            subject=f"Kontaktanfrage von {from_user.full_name}",
            message=(
                f"{from_user.full_name} ({from_user.email}) möchte Kontakt "
                f"mit dir aufnehmen.\n\n{contact.message}"
            ),
            html_message=html_message,
            to=to_user.email,
        )
    except ResendError as exc:
        contact.status = ContactRequestStatus.FAILED
        contact.save(update_fields=["status"])
        if exc.retryable:
            raise self.retry(exc=exc)
        logger.error(
            "Kontaktanfrage %s dauerhaft nicht zustellbar: %s", contact.pk, exc
        )
        raise
    else:
        contact.status = ContactRequestStatus.SENT
        contact.save(update_fields=["status"])
