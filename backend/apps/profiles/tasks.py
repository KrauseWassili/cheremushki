from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import ContactRequest, ContactRequestStatus


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

    try:
        html_message = render_to_string(
            "emails/contact_request.html",
            {
                "from_user": from_user,
                "to_user": to_user,
                "message": contact.message,
            },
        )
        send_mail(
            subject=f"Kontaktanfrage von {from_user.full_name}",
            message=(
                f"{from_user.full_name} ({from_user.email}) möchte Kontakt "
                f"mit dir aufnehmen.\n\n{contact.message}"
            ),
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_user.email],
        )
        contact.status = ContactRequestStatus.SENT
        contact.save(update_fields=["status"])
    except Exception as exc:
        contact.status = ContactRequestStatus.FAILED
        contact.save(update_fields=["status"])
        raise self.retry(exc=exc)
