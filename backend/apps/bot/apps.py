from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Warning as CheckWarning
from django.core.checks import register


class BotConfig(AppConfig):
    name = "apps.bot"

    def ready(self):
        register(check_telegram_configuration)


def check_telegram_configuration(app_configs, **kwargs):
    """
    Meldet fehlende Telegram Konfiguration beim Start statt beim ersten Call.

    Ohne Token entsteht die URL …/bot/<method> und jeder Aufruf scheitert
    mit einer Meldung, die nicht nach "Konfiguration fehlt" aussieht.
    """
    problems = []
    if not getattr(settings, "TELEGRAM_BOT_TOKEN", ""):
        problems.append(
            CheckWarning(
                "TELEGRAM_BOT_TOKEN ist leer – alle Bot-Aufrufe schlagen fehl.",
                hint="TELEGRAM_BOT_TOKEN in der .env setzen.",
                id="bot.W001",
            )
        )
    if not getattr(settings, "TELEGRAM_CHAT_ID", ""):
        problems.append(
            CheckWarning(
                "TELEGRAM_CHAT_ID ist leer – Invites und Profilposts schlagen fehl.",
                hint="TELEGRAM_CHAT_ID in der .env setzen.",
                id="bot.W002",
            )
        )
    return problems
