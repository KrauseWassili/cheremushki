"""
Deploy-Checks gegen Platzhalter- und schwache Secrets.

config ist keine App: Registriert wird über AccountsConfig.ready(), weil
SECRET_KEY vor allem die JWTs und Reset-/Aktivierungs-Tokens von accounts
signiert. is_weak_secret nutzen auch die Checks in bot und accounts.

Alle Checks hier sind deploy=True und schweigen bei DEBUG=True: Der
Test-Runner setzt DEBUG=False, ohne dass die Test-.env echte Secrets hat –
als normaler Check würde jeder Testlauf rot.
"""

from django.conf import settings
from django.core.checks import Error, Tags, register

# Werte aus .env.stage.example und typische Vorlagen. Als Teilstring geprüft,
# kleingeschrieben – "django-insecure-…" ist der Default von startproject.
_PLACEHOLDER_MARKERS = ("todo_set_me", "changeme", "change_me", "change-me", "insecure")
# Nur exakt: Als Teilstring kämen sie in Zufallswerten zu leicht vor.
_PLACEHOLDER_VALUES = frozenset({"secret", "password", "test", "dummy", "xxx"})
# Djangos eigene Schwelle (security.W009), dort nur als Warning.
MIN_SECRET_KEY_LENGTH = 50

SECRET_KEY_HINT = (
    "Zufälligen Wert setzen, z. B. "
    '`python -c "import secrets; print(secrets.token_urlsafe(50))"`. Achtung: '
    "Ein neuer SECRET_KEY macht alle ausgegebenen JWTs und offenen "
    "Reset-/Aktivierungslinks ungültig."
)


def is_weak_secret(value: str, *, min_length: int) -> bool:
    """
    Platzhalter, bekannter Vorlagenwert oder zu kurz?
    """
    normalized = value.strip().lower()
    return (
        len(normalized) < min_length
        or normalized in _PLACEHOLDER_VALUES
        or any(marker in normalized for marker in _PLACEHOLDER_MARKERS)
    )


@register(Tags.security, deploy=True)
def check_secret_key(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    if not is_weak_secret(settings.SECRET_KEY, min_length=MIN_SECRET_KEY_LENGTH):
        return []
    return [
        Error(
            "SECRET_KEY ist ein Platzhalter oder kürzer als "
            f"{MIN_SECRET_KEY_LENGTH} Zeichen – JWTs und Reset-Links wären "
            "fälschbar.",
            hint=SECRET_KEY_HINT,
            id="config.E001",
        )
    ]
