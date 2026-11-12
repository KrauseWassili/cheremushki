"""
Erzeugung der Profil-Slugs für /members/<slug>.

Djangos slugify() ohne allow_unicode verwirft kyrillische Zeichen komplett –
"Анна Тестова" ergab einen leeren Slug, und der alte Fallback member-<user_id>
griff für praktisch jedes Mitglied (E2E F6). Das legte die fortlaufende
User-ID offen und damit die Mitgliederzahl. Deshalb wird vorher in lateinische
Buchstaben umgeschrieben, und der Fallback ist zufällig statt aus der PK
abgeleitet.

Bewusst ohne I/O und ohne Modellimport: Die Datenmigration 0009 nutzt dieselben
Funktionen, darf aber keine echten Modelle importieren.
"""

import secrets
from collections.abc import Callable

from django.utils.text import slugify

# Slugs, die im Verzeichnis-Router bereits eine Route belegen. Der Router
# registriert MemberProfileViewSet als Catch-all unter api/v1/profiles/ – ein
# Mitglied mit dem Slug "tags" wäre unter /profiles/tags/ nicht erreichbar,
# weil dort die @action liegt. Deshalb werden diese Slugs gar nicht erst
# vergeben.
RESERVED_SLUGS: frozenset[str] = frozenset({"user", "tags", "cities"})

# MemberProfile.slug hat max_length=80. Die Basis bleibt darunter, damit der
# Zähler-Suffix ("-2", "-17", …) bei Kollisionen noch in die Spalte passt.
# Nötig, weil die Umschrift länger wird als das Original (щ -> shch).
MAX_SLUG_BASE_LENGTH = 72

FALLBACK_SLUG_PREFIX = "member"
# 4 Byte = 8 Hex-Zeichen: genug, dass Kollisionen praktisch nicht vorkommen,
# und falls doch, löst sie der Zähler in unique_slug() auf.
FALLBACK_SLUG_TOKEN_BYTES = 4

# Einfache, lesbare Umschrift statt einer Norm wie ISO 9 – der Slug soll sich
# vorlesen und abtippen lassen, nicht rückübersetzbar sein. Russisch plus die
# ukrainischen und belarussischen Sonderbuchstaben. Nur Kleinbuchstaben: die
# Eingabe wird vorher mit lower() gefaltet.
_CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    # Ukrainisch
    "і": "i",
    "ї": "yi",
    "є": "ye",
    "ґ": "g",
    # Belarussisch
    "ў": "u",
}
_TRANSLITERATION_TABLE = str.maketrans(_CYRILLIC_TO_LATIN)


def transliterate(text: str) -> str:
    """
    Schreibt kyrillische Buchstaben in lateinische um.

    Gibt den Text kleingeschrieben zurück. Alles außerhalb der Tabelle bleibt
    unverändert – lateinische Namen und Akzente ("Zoë") behandelt danach
    slugify().
    """
    return text.lower().translate(_TRANSLITERATION_TABLE)


def slug_base(source: str) -> str:
    """
    Leitet aus einem Namen die Slug-Basis ab, ohne Eindeutigkeit zu prüfen.

    Bleibt nach der Umschrift nichts übrig (nur Emoji, nur Satzzeichen,
    andere Schriften), kommt ein zufälliger member-<hex>-Slug zurück – nie
    etwas aus der User-ID.
    """
    base = slugify(transliterate(source))[:MAX_SLUG_BASE_LENGTH].strip("-")
    if base:
        return base
    return f"{FALLBACK_SLUG_PREFIX}-{secrets.token_hex(FALLBACK_SLUG_TOKEN_BYTES)}"


def unique_slug(base: str, is_taken: Callable[[str], bool]) -> str:
    """
    Hängt an die Basis "-2", "-3", … bis der Slug frei ist.

    Der Zähler verrät nur, wie viele Mitglieder denselben Namen tragen, nicht
    die User-ID. is_taken kapselt die Datenbankabfrage, damit Modell und
    Datenmigration dieselbe Logik nutzen. Reservierte Slugs verhalten sich wie
    belegte: Ein Mitglied namens "Tags" weicht auf "tags-2" aus.
    """
    candidate = base
    counter = 2
    while candidate in RESERVED_SLUGS or is_taken(candidate):
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate
