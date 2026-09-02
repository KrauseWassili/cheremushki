"""
Validierung von Hashtag-Tokens.

Valide Form: lowercase, ohne führendes '#', nur Unicode-Buchstaben,
Ziffern und '_'.

Warum das nötig ist: Die Mitglieder suchen im Telegram-Kanal über Hashtags.
Telegrams Hashtag-Parser beendet ein Token beim ersten Zeichen, das weder
Buchstabe noch Ziffer noch '_' ist – aus "#веб-разработка" wird im Client also
ein anklickbares "#веб", der Rest bleibt Fließtext. Ein Tag, der im Post anders
aussieht als in der Suche, ist als Suchbegriff wertlos. Deshalb wird schon beim
Speichern validiert und nicht erst beim Rendern: Nur so sind das, was der
Nutzer im Verzeichnis filtert, und das, was er in Telegram anklickt, derselbe
String.

Dieselbe Validierung trägt die Stadt, die im Profilpost ebenfalls als
Hashtag erscheint ("Бремен" -> "#бремен").
"""

import re
import unicodedata

# Telegram schneidet lange Hashtags nicht ab, aber jenseits dieser Länge ist
# ein Tag als gemeinsamer Suchbegriff einer Community ohnehin nicht mehr
# brauchbar. Bleibt unter TagBase.name (max_length=100), damit die
# valide Form immer in die Spalte passt.
MAX_HASHTAG_LENGTH = 64

# Beide Varianten des Doppelkreuzes: ASCII '#' und das fullwidth '＃', das
# über mobile Tastaturen (CJK-Layouts) in Eingaben gerät.
_HASH_PREFIXES = ("#", "＃")

# Zeichen, die im Sprachgebrauch Wörter trennen und deshalb zu '_' werden,
# statt den Tag zu zerreißen: "Веб-разработка" -> "веб_разработка".
_SEPARATOR_RE = re.compile(r"[\s\-–—·•./,:;|]+")

# Was danach noch übrig bleibt und kein Buchstabe, keine Ziffer und kein '_'
# ist (Emojis, Satzzeichen, Klammern), wird verworfen.
_DISALLOWED_RE = re.compile(r"[^\w]", re.UNICODE)

_MULTIPLE_UNDERSCORES_RE = re.compile(r"_{2,}")


class InvalidHashtag(ValueError):
    """
    Der Wert lässt sich nicht zu einem Hashtag Token auflösen.
    """


def parse_hashtag(value: str | None) -> str:
    """
    Löst Nutzereingaben zur validen Hashtag-Form auf.

    Akzeptiert "#IT", "IT", "Веб Разработка", "крипта!!!" und liefert
    "it", "it", "веб_разработка", "крипта".
    """
    raw = value or ""

    # NFKC zieht Kompatibilitätsformen zusammen (fullwidth Latin, Ligaturen).
    # Ohne diesen Schritt wären "ＩＴ" und "IT" zwei verschiedene Tags.
    raw = unicodedata.normalize("NFKC", raw).strip()

    for prefix in _HASH_PREFIXES:
        raw = raw.removeprefix(prefix)
    raw = raw.strip()

    if not raw:
        raise InvalidHashtag("Wert ist leer")

    # --- casefold() statt lower(): korrekt auch für Kyrillisch und das deutsche ß.
    token = raw.casefold()
    token = _SEPARATOR_RE.sub("_", token)
    token = _DISALLOWED_RE.sub("", token)
    token = _MULTIPLE_UNDERSCORES_RE.sub("_", token).strip("_")

    if not token:
        raise InvalidHashtag(f"Kein verwertbares Zeichen enthalten: {value!r}")

    # Rein numerische Hashtags erkennt Telegram nicht als Hashtag "#2024"
    # bleibt im Post Fließtext und wäre damit ein toter Suchbegriff.
    if not any(character.isalpha() for character in token):
        raise InvalidHashtag(f"Enthält keinen Buchstaben: {value!r}")

    if len(token) > MAX_HASHTAG_LENGTH:
        raise InvalidHashtag(f"Länger als {MAX_HASHTAG_LENGTH} Zeichen: {value!r}")

    return token


def normalize_hashtag(value: str | None) -> str | None:
    """
    Für Renderpfade gedacht: Dass sich eine Stadt nicht zu einem Hashtag
    auflösen lässt, ist kein Grund, den ganzen Profilpost scheitern zu lassen.
    Der Aufrufer entscheidet dann über den Fallback.
    """
    try:
        return parse_hashtag(value)
    except InvalidHashtag:
        return None


def build_hashtag(token: str) -> str:
    """
    Setzt das '#' vor ein bereits valides Token.

    Die gespeicherte und über die API
    ausgelieferte Form trägt kein '#' das gehört zur Darstellung.
    """
    return f"#{token}"
