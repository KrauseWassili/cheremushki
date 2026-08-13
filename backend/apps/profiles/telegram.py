"""Kanonisierung und Validierung von Telegram-Usernamen.

Kanonische Form: bare, lowercase, ohne '@' und ohne URL-Rahmen.

Warum das nötig ist: Der Profilpost in der Telegram-Gruppe enthält einen
URL-Button auf https://t.me/<username>. Telegram beantwortet einen
ungültigen Button mit BUTTON_URL_INVALID und lässt damit den kompletten
sendPhoto-Call scheitern – nicht nur den Button. Zusätzlich ist das Feld über
die API frei beschreibbar das Charset-Gate hier ist die Grenze, die verhindert,
dass ein Mitglied den Button aus einem offiziellen Club-Post heraus auf eine
fremde Domain zeigen lässt.
"""

import re
from urllib.parse import urlsplit

# Sicherheitsgrenze: Was hier durchkommt, ist in einer URL unbedenklich.
# Untergrenze 4, weil über Fragment versteigerte Handles vier Zeichen kurz sein
# können die 5 Zeichen-Regel gilt nur für frei registrierte Namen.
_CHARSET_RE = re.compile(r"[A-Za-z0-9_]{4,32}")

# Fachregel: Telegrams Namensvergabe. Buchstabe am Anfang, '_' nur zwischen
# alphanumerischen Gruppen – deckt '__' und ein abschließendes '_' zugleich ab.
_SHAPE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*")

_ALLOWED_HOSTS = frozenset({"t.me", "telegram.me", "telegram.dog"})

# Erste Pfadsegmente von t.me, die kein Profil bezeichnen.
_RESERVED = frozenset(
    {
        "joinchat",
        "proxy",
        "socks",
        "share",
        "login",
        "addstickers",
        "addtheme",
        "addemoji",
        "setlanguage",
        "confirmphone",
    }
)


class InvalidTelegramUsername(ValueError):
    """
    Der Wert lässt sich nicht zu einem Telegram-Usernamen auflösen.
    """


def parse_telegram_username(value: str | None, *, strict: bool = True) -> str:
    """
    Löst Nutzereingaben zur kanonischen Form auf.

    Akzeptiert durov, @durov, t.me/durov,
    https://t.me/durov?start=x und Varianten mit http, www. sowie
    telegram.me.

    Args:
        value: Rohe Eingabe, darf None sein.
        strict: Prüft zusätzlich Telegrams Formregeln (Beginn mit Buchstabe,
            kein abschließendes _, keine doppelten __). Für
            Nutzereingaben True – dort wollen wir früh und deutlich
            melden. Für bereits gespeicherte Altbestände False, damit
            Legacy-Handles aus der Zeit vor Telegrams Regelverschärfung
            nutzbar bleiben.

    Returns:
        Den Usernamen ohne @, in Kleinschreibung.

    Raises:
        InvalidTelegramUsername: Wenn der Wert leer oder unbrauchbar ist.
    """
    raw = (value or "").strip()
    if not raw:
        raise InvalidTelegramUsername("Wert ist leer")

    # Ein '@' kann vor der ganzen Eingabe stehen ('@https://t.me/durov') oder
    # vor dem Handle im Link ('https://t.me/@durov') beides kommt vor.
    candidate = _unwrap_url(raw.removeprefix("@")).removeprefix("@").strip()

    if not _CHARSET_RE.fullmatch(candidate):
        raise InvalidTelegramUsername(f"Ungültiges Format: {candidate!r}")
    if strict and not _SHAPE_RE.fullmatch(candidate):
        raise InvalidTelegramUsername(
            f"Verstößt gegen Telegrams Namensregeln: {candidate!r}"
        )

    username = candidate.lower()
    if username in _RESERVED:
        raise InvalidTelegramUsername(f"Reservierter Name: {username!r}")
    return username


def normalize_telegram_username(value: str | None) -> str | None:
    """
    Wie :func:parse_telegram_username, aber None statt Exception.

    Für Renderpfade gedacht, in denen ein fehlender Button kein Grund ist, die
    ganze Operation scheitern zu lassen. Läuft bewusst mit strict=False:
    hier geht es nur darum, ob sich ein Link bauen lässt.
    """
    try:
        return parse_telegram_username(value, strict=False)
    except InvalidTelegramUsername:
        return None


def build_telegram_dm_url(username: str) -> str:
    """
    Baut den Direktnachricht Link.

    Validiert erneut, das ist keine Doppelung, sondern die Garantie, dass kein
    f-String mit ungeprüftem Inhalt in eine Telegram-URL gerät, egal wer diese
    Funktion künftig aufruft.
    """
    return f"https://t.me/{parse_telegram_username(username, strict=False)}"


def _unwrap_url(raw: str) -> str:
    """
    Zieht das Username-Segment aus einem t.me-Link. Kein Link unverändert.
    """
    if "/" not in raw:
        return raw

    # urlsplit braucht '//', um den Host zu erkennen: 't.me/durov' → '//t.me/durov'
    url = raw if "//" in raw else f"//{raw}"
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").removeprefix("www.")
    except ValueError as exc:  # kaputte Netloc, z. B. ungültiger Port
        raise InvalidTelegramUsername(f"Nicht parsebar: {raw!r}") from exc

    if parts.scheme not in ("", "http", "https"):
        raise InvalidTelegramUsername(f"Schema nicht erlaubt: {parts.scheme!r}")
    if host not in _ALLOWED_HOSTS:
        raise InvalidTelegramUsername(f"Host nicht erlaubt: {host!r}")

    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) != 1:
        # 0 Segmente = nur der Host; >1 = Nachrichten-Link wie /durov/123
        raise InvalidTelegramUsername(f"Kein Profil-Link: {raw!r}")
    return segments[0]
