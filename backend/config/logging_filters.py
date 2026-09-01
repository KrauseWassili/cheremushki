"""
Maskierung von Secrets in Log Ausgaben.

Zweite Verteidigungslinie: Die erste ist, Secrets gar nicht erst in eine
Exception zu schreiben (siehe apps/bot/services/telegram.py). Diese hier
greift, wenn doch eine Bibliothek eine URL mit Token in eine Meldung oder einen
Traceback schreibt.

Die Maskierung sitzt im Formatter und nicht in einem Filter, weil der Formatter
die einzige Stelle ist, an der Message, Argumente und Traceback bereits zu
einem String zusammengesetzt sind.
"""

from __future__ import annotations

import logging
import re

# https://api.telegram.org/bot<bot_id>:<secret>/<method>
_TELEGRAM_TOKEN_RE = re.compile(r"bot\d{6,}:[A-Za-z0-9_\-]{20,}")

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_TELEGRAM_TOKEN_RE, "bot<redacted>"),
)


def mask_secrets(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SecretMaskingFormatter(logging.Formatter):
    """
    Formatter, der bekannte Secret Muster aus der fertigen Zeile entfernt.
    """

    def format(self, record: logging.LogRecord) -> str:
        return mask_secrets(super().format(record))
