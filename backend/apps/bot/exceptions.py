"""
Fehlertypen für die Telegram-Bot-API.

Die Bot-API antwortet strukturiert (error_code, description, parameters.retry_after).
Diese Information darf nicht in einem f-String
verschwinden.

Der Textvergleich in :meth: TelegramAPIError.is_not_modified und
:meth: ~TelegramAPIError.is_message_gone bleibt bestehen: Telegram liefert für
all diese Fälle error_code: 400, unterscheidbar sind sie nur über die
englische Beschreibung. Der Unterschied ist, dass der Vergleich hier an genau
einer Stelle steht, einen Namen hat und ohne HTTP-Mock testbar ist.
"""

from __future__ import annotations


class TelegramError(RuntimeError):
    """
    Basisklasse für alle Fehler der Telegram-Anbindung.
    """


class TelegramConfigurationError(TelegramError):
    """
    Die Anbindung ist nicht vollständig konfiguriert (Token, Chat, Topic).
    """


class TelegramTransportError(TelegramError):
    """
    Die Anfrage hat Telegram nicht erreicht oder blieb ohne Antwort.

    Trägt bewusst weder die URL noch die ursprüngliche requests Exception:
    beide enthalten den Bot-Token, und diese Exception wird geloggt.
    """


class TelegramAPIError(TelegramError):
    """
    Telegram hat geantwortet, aber mit ok: false.
    """

    def __init__(self, method: str, status_code: int, payload: dict) -> None:
        self.method = method
        self.status_code = status_code
        self.error_code = payload.get("error_code")
        self.description = str(payload.get("description") or "")
        self.retry_after = (payload.get("parameters") or {}).get("retry_after")
        super().__init__(
            f"Telegram {method} fehlgeschlagen "
            f"(HTTP {status_code}, code {self.error_code}): {self.description}"
        )

    @property
    def is_not_modified(self) -> bool:
        """
        Der Post ist inhaltlich unverändert für uns ein Erfolg.
        """
        return "message is not modified" in self.description.lower()

    @property
    def is_message_gone(self) -> bool:
        """
        Die Nachricht existiert nicht mehr oder ist nicht mehr bearbeitbar.
        Nur in diesem Fall ist ein neuer Post die richtige Reaktion.
        """
        text = self.description.lower()
        return any(
            marker in text
            for marker in (
                "message to edit not found",
                "message can't be edited",
                "message identifier is not specified",
                "message_id_invalid",
            )
        )

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429 or self.retry_after is not None
