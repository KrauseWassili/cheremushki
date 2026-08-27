from django.apps import AppConfig


class BotConfig(AppConfig):
    name = "apps.bot"

    def ready(self):
        # --- Die Checks registrieren sich per Decorator selbst
        from apps.bot import checks  # noqa: F401
