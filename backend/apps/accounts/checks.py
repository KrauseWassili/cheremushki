"""
Konfigurationschecks des Mailversands (Resend).
"""

from django.conf import settings
from django.core.checks import Error, register

from config.checks import is_weak_secret

# Eigener Tag statt Tags.compatibility: Die Meldung betrifft den Mailversand,
# nicht die Kompatibilität – und `check --tag email` prüft gezielt nur das.
EMAIL_CHECK_TAG = "email"

# Resend vergibt Keys immer mit diesem Präfix – alles andere ist ein
# Platzhalter oder ein vertauschter Wert.
RESEND_KEY_PREFIX = "re_"
# Nur "mehr als das Präfix": Resend dokumentiert keine feste Länge, eine
# geratene Schwelle würde einen echten Key irgendwann ablehnen.
MIN_RESEND_KEY_LENGTH = len(RESEND_KEY_PREFIX) + 1

RESEND_HINT = (
    "In der .env setzen. Die Absender-Domain muss in Resend verifiziert sein "
    "(SPF/DKIM), sonst lehnt Resend jede Mail mit 4xx ab."
)


# deploy=True: Djangos Test-Runner setzt DEBUG=False, bevor er die
# System-Checks ausführt. Als normaler Check würde dieser Error jeden
# Testlauf ohne Resend-Key (CI, lokal) abbrechen. So greift er gezielt bei
# `manage.py check --deploy`.
@register(EMAIL_CHECK_TAG, deploy=True)
def check_resend_configuration(app_configs, **kwargs):
    """
    Ohne Key oder Absender schlägt in Produktion jede Mail fehl
    (Aktivierung, Passwort-Reset, Einladung) – bisher nur als Log-Zeile im
    Worker sichtbar. Mit DEBUG=True kein Problem: send_email() stellt dann
    lokal per SMTP an mailcatcher zu.
    """
    if settings.DEBUG:
        return []

    problems = []
    if not settings.RESEND_API_KEY:
        problems.append(
            Error(
                "RESEND_API_KEY ist leer – mit DEBUG=False geht keine E-Mail raus.",
                hint=RESEND_HINT,
                id="accounts.E001",
            )
        )
    elif not settings.RESEND_API_KEY.startswith(RESEND_KEY_PREFIX) or is_weak_secret(
        settings.RESEND_API_KEY, min_length=MIN_RESEND_KEY_LENGTH
    ):
        problems.append(
            Error(
                "RESEND_API_KEY sieht nicht nach einem Resend-Key aus "
                f"(Präfix {RESEND_KEY_PREFIX!r} fehlt oder Platzhalter).",
                hint=RESEND_HINT,
                id="accounts.E003",
            )
        )
    if not settings.RESEND_FROM_EMAIL:
        problems.append(
            Error(
                "RESEND_FROM_EMAIL ist leer – mit DEBUG=False geht keine E-Mail raus.",
                hint=RESEND_HINT,
                id="accounts.E002",
            )
        )
    return problems
