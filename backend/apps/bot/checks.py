"""
Konfigurationschecks der Telegram-Anbindung.
"""

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

SECRET_HINT = (
    'Ein zufälliges Secret setzen (z. B. `python -c "import secrets; '
    'print(secrets.token_urlsafe(32))"`) und denselben Wert bei '
    "`manage.py set_telegram_webhook --url …` verwenden."
)


@register(Tags.compatibility)
def check_telegram_credentials(app_configs, **kwargs):
    """Token und Chat-ID – ohne sie schlägt jeder Bot-Aufruf fehl."""
    problems = []

    if not getattr(settings, "TELEGRAM_BOT_TOKEN", ""):
        problems.append(
            Warning(
                "TELEGRAM_BOT_TOKEN ist leer – alle Bot-Aufrufe schlagen fehl.",
                hint="TELEGRAM_BOT_TOKEN in der .env setzen.",
                id="bot.W001",
            )
        )

    if not getattr(settings, "TELEGRAM_CHAT_ID", ""):
        problems.append(
            Warning(
                "TELEGRAM_CHAT_ID ist leer – Invites und Profilposts schlagen " "fehl.",
                hint="TELEGRAM_CHAT_ID in der .env setzen.",
                id="bot.W002",
            )
        )

    return problems


@register(Tags.security)
def check_webhook_secret(app_configs, **kwargs):
    """Das Webhook-Secret.

    Ein leeres Secret ist mit DEBUG=False ein Error und keine Warnung:
    IsTelegramWebhook lehnt dann jede Anfrage ab, der Webhook ist also
    nicht bloß unsicher, sondern funktionslos. Als Error bricht
    manage.py check --deploy ab, bevor deployed wird.
    """
    if getattr(settings, "TELEGRAM_UPDATE_MODE", "polling") != "webhook":
        return []
    if getattr(settings, "TELEGRAM_WEBHOOK_SECRET", ""):
        return []

    message = "TELEGRAM_WEBHOOK_SECRET ist leer – der Webhook lehnt jede Anfrage ab."
    if settings.DEBUG:
        return [Warning(message, hint=SECRET_HINT, id="bot.W003")]
    return [Error(message, hint=SECRET_HINT, id="bot.E001")]


@register(Tags.compatibility)
def check_update_mode_matches_configuration(app_configs, **kwargs):
    """
    Meldet einen Webhook-Modus ohne erreichbare https-Basis.

    Telegram akzeptiert nur https-Webhooks. Steht der Modus auf webhook,
    während FRONTEND_URL auf localhost zeigt, ist die Registrierung
    vermutlich nie erfolgt und, dann verarbeitet niemand Updates, weil der
    Poller im Webhook-Modus stillsteht.
    """
    if getattr(settings, "TELEGRAM_UPDATE_MODE", "polling") != "webhook":
        return []

    frontend = str(getattr(settings, "FRONTEND_URL", ""))
    if frontend.startswith("https://"):
        return []

    return [
        Warning(
            f"TELEGRAM_UPDATE_MODE ist 'webhook', FRONTEND_URL ist aber "
            f"{frontend!r} – Telegram akzeptiert nur https-Webhooks.",
            hint=(
                "Entweder TELEGRAM_UPDATE_MODE=polling setzen oder eine "
                "öffentliche https-URL bereitstellen (lokal z. B. per "
                "`cloudflared tunnel --url http://localhost:8000`). Stand "
                "prüfen mit `manage.py set_telegram_webhook --info`."
            ),
            id="bot.W004",
        )
    ]
