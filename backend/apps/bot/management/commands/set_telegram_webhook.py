"""
Registriert oder entfernt den Telegram-Webhook.

Warum als Command und nicht per curl: Der Aufruf braucht den Bot-Token, und
der soll nicht in der Shell-History landen. Zusätzlich prüft das Command, dass
die Registrierung zum konfigurierten TELEGRAM_UPDATE_MODE passt.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django.urls import reverse

from apps.bot.exceptions import TelegramError
from apps.bot.services.telegram import (
    ALLOWED_UPDATE_TYPES,
    delete_webhook,
    get_webhook_info,
    set_webhook,
)


class Command(BaseCommand):
    help = (
        "Registriert den Telegram-Webhook (--url), entfernt ihn (--delete) "
        "oder zeigt den aktuellen Stand (--info)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            help=(
                "Öffentliche https-Basis-URL ohne Pfad, z. B. "
                "https://cheremushki.example"  # Todo: entweder .env oder hier später ändern
            ),
        )
        parser.add_argument("--delete", action="store_true", help="Webhook entfernen")
        parser.add_argument("--info", action="store_true", help="Nur Status anzeigen")

    def handle(self, *args, **options):
        try:
            if options["info"]:
                return self._show_info()
            if options["delete"]:
                return self._delete()
            return self._register(options["url"])
        except TelegramError as exc:
            # Deckt API-, Transport- und Konfigurationsfehler ab – alle drei
            # erben von TelegramError und sollen als CommandError erscheinen.
            raise CommandError(str(exc)) from None

    def _show_info(self) -> None:
        info = get_webhook_info()
        url = info.get("url") or "(keiner registriert)"
        self.stdout.write(f"Webhook-URL:            {url}")
        self.stdout.write(f"Secret gesetzt:         {bool(info.get('url'))}")
        self.stdout.write(f"Ausstehende Updates:    {info.get('pending_update_count')}")
        if info.get("last_error_message"):
            self.stdout.write(
                self.style.WARNING(
                    f"Letzter Fehler:         {info['last_error_message']}"
                )
            )
        self.stdout.write(f"TELEGRAM_UPDATE_MODE:   {settings.TELEGRAM_UPDATE_MODE}")

        if bool(info.get("url")) != (settings.TELEGRAM_UPDATE_MODE == "webhook"):
            self.stdout.write(
                self.style.ERROR(
                    "Registrierung und TELEGRAM_UPDATE_MODE passen nicht "
                    "zusammen – entweder Updates werden gar nicht verarbeitet "
                    "oder der Poller läuft ins 409."
                )
            )

    def _delete(self) -> None:
        delete_webhook()
        self.stdout.write(self.style.SUCCESS("Webhook entfernt."))
        if settings.TELEGRAM_UPDATE_MODE == "webhook":
            self.stdout.write(
                self.style.WARNING(
                    "TELEGRAM_UPDATE_MODE steht noch auf 'webhook' – ohne "
                    "Registrierung werden jetzt keine Updates verarbeitet. "
                    "Auf 'polling' umstellen und Beat neu starten."
                )
            )

    def _register(self, base_url: str | None) -> None:
        if not base_url:
            raise CommandError("--url, --delete oder --info angeben.")

        base_url = base_url.rstrip("/")
        if not base_url.startswith("https://"):
            raise CommandError(
                f"Telegram akzeptiert nur https-Webhooks, nicht {base_url!r}."
            )

        # Das leere Secret prüft set_webhook selbst – dort gilt es auch für
        # Aufrufe aus der Shell. Hier bleibt, was Sache des Bedieners ist:
        # Reihenfolge und Erreichbarkeit.
        if settings.TELEGRAM_UPDATE_MODE != "webhook":
            raise CommandError(
                "TELEGRAM_UPDATE_MODE steht auf "
                f"{settings.TELEGRAM_UPDATE_MODE!r}. Der Endpunkt lehnt in "
                "diesem Modus jede Anfrage ab – erst umstellen, dann "
                "registrieren."
            )

        # Pfad aus dem Router ableiten, nicht hartcodieren: Sonst zeigt die
        # Registrierung bei einer Änderung an apps/bot/routers.py ins Leere,
        # und Telegram meldet nur 404 ohne Hinweis auf die Ursache.
        url = f"{base_url}{reverse('telegram-webhook-list')}"
        set_webhook(url)
        self.stdout.write(self.style.SUCCESS(f"Webhook registriert: {url}"))
        self.stdout.write(f"Erlaubte Update-Typen: {', '.join(ALLOWED_UPDATE_TYPES)}")
