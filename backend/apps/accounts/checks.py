"""
Konfigurationschecks des Mailversands (Resend).
"""

from django.conf import settings
from django.core.checks import Error, register

# Eigener Tag statt Tags.compatibility: Die Meldung betrifft den Mailversand,
# nicht die Kompatibilität – und `check --tag email` prüft gezielt nur das.
EMAIL_CHECK_TAG = "email"

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
    if not settings.RESEND_FROM_EMAIL:
        problems.append(
            Error(
                "RESEND_FROM_EMAIL ist leer – mit DEBUG=False geht keine E-Mail raus.",
                hint=RESEND_HINT,
                id="accounts.E002",
            )
        )
    return problems
