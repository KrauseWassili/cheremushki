from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"

    def ready(self):
        # --- Die Checks registrieren sich per Decorator selbst
        from apps.accounts import checks  # noqa: F401

        # SECRET_KEY-Check (config ist keine App), siehe config/checks.py.
        from config import checks as config_checks  # noqa: F401
