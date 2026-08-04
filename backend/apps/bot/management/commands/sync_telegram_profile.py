from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import CustomUser
from apps.bot.models import TelegramInvite
from apps.bot.tasks.profile_post import sync_telegram_profile_post


class Command(BaseCommand):
    help = (
        "Profilkarte in Telegram «Наши люди» synchronisieren. "
        "Optional Beitritt nachtragen, falls Invite fehlt."
    )

    def add_arguments(self, parser):
        parser.add_argument("user", help="User-ID oder E-Mail")
        parser.add_argument(
            "--telegram-user-id",
            type=int,
            default=None,
            help="Telegram-User-ID setzen und Invite als used markieren",
        )
        parser.add_argument(
            "--eager",
            action="store_true",
            help="Direkt ausführen statt Celery-Queue",
        )

    def handle(self, *args, **options):
        raw = options["user"]
        try:
            user = CustomUser.objects.get(pk=int(raw))
        except (CustomUser.DoesNotExist, ValueError):
            user = CustomUser.objects.filter(email__iexact=raw).first()
        if user is None:
            raise CommandError(f"User nicht gefunden: {raw}")

        if not user.is_active:
            raise CommandError("User ist nicht aktiv (E-Mail-Aktivierung fehlt).")

        invite, _ = TelegramInvite.objects.get_or_create(user=user)
        tg_id = options["telegram_user_id"]
        if tg_id is not None:
            conflict = (
                TelegramInvite.objects.filter(telegram_user_id=tg_id)
                .exclude(pk=invite.pk)
                .first()
            )
            if conflict:
                raise CommandError(
                    f"Telegram-User-ID {tg_id} ist bereits an user={conflict.user_id} gebunden."
                )
            invite.telegram_user_id = tg_id
            invite.used = True
            from django.utils import timezone

            invite.used_at = invite.used_at or timezone.now()
            invite.save(
                update_fields=["telegram_user_id", "used", "used_at"]
            )
            self.stdout.write(
                self.style.WARNING(
                    f"Invite für user={user.pk} als used markiert (tg={tg_id})."
                )
            )

        if not invite.used:
            raise CommandError(
                "Invite ist noch nicht used. Entweder erst der Gruppe beitreten "
                "oder --telegram-user-id setzen."
            )

        if options["eager"]:
            sync_telegram_profile_post.apply(args=[user.pk])
            invite.refresh_from_db()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sync fertig. message_id={invite.profile_message_id}"
                )
            )
        else:
            sync_telegram_profile_post.delay(user.pk)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sync-Task für user={user.pk} in die Queue gelegt."
                )
            )
