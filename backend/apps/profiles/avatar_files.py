"""
Ablage, Bereinigung und Aufräumen der Avatar-Dateien.

Eigenes Modul ohne Modellimport: models.py braucht die Pfadkonstanten und die
Aufräumfunktionen für anonymize(), ein Import in die Gegenrichtung wäre
zirkulär.
"""

import io
import logging
import posixpath
import re
import struct
import warnings
from collections.abc import Iterable
from functools import partial

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Öffentlich ausgelieferter Zuschnitt und privates Original liegen getrennt:
# config.views.public_media verweigert alles unter AVATAR_ORIGINALS_DIR, das
# Original bekommt nur der Eigentümer über die API.
AVATAR_DIR = "avatars"
AVATAR_ORIGINALS_DIR = f"{AVATAR_DIR}/originals"

# Vor den Zufallsnamen hießen Avatare avatars/user-<id>.<ext> (plus Djangos
# Kollisionsvarianten user-<id>_AbC123x.<ext>). Verankert, damit nur das alte
# Schema passt und keine Zufallsnamen. Hier und nicht in legacy_avatars.py:
# config.views.public_media sperrt dieselben Namen, ohne Modelle zu laden.
_LEGACY_FILE_NAME = re.compile(r"^user-\d+(?:_[A-Za-z0-9]+)?\.[A-Za-z0-9]+$")

# Allowlist: Pillow öffnet nur diese Formate, alle anderen Plugins (GIF, BMP,
# TIFF, PSD, …) – und damit deren Parser-Angriffsfläche – bleiben außen vor.
# Das Format bleibt beim Neuschreiben erhalten, Endung und Inhalt passen also
# zusammen (upload_to lässt ohnehin nur diese Endungen zu).
ALLOWED_AVATAR_FORMATS = ("JPEG", "PNG", "WEBP")
_EXTENSION_BY_FORMAT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
# Dateisignaturen derselben drei Formate. WebP: "RIFF", 4 Byte Länge, "WEBP".
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SIGNATURE_PROBE_BYTES = 12
# Wie der Zuschnitt im Frontend (canvas.toBlob(..., 0.92)) – sichtbar kein
# Unterschied, ein erneutes Kodieren ist für das Entfernen der Metadaten nötig.
_JPEG_QUALITY = 90
_WEBP_QUALITY = 90

# Obergrenzen gegen Speicher-DoS: Eine wenige KB große PNG kann sich beim
# Dekodieren auf Gigabytes aufblähen. Die Byte-Grenze prüft der Serializer vor
# dem Öffnen, die Pixelgrenze greift nach Image.open (liest nur den Header)
# und vor load()/exif_transpose (dekodieren das ganze Bild). 16 MP deckt jede
# Handykamera ab und liegt weit unter Pillows eigener Schwelle
# (Image.MAX_IMAGE_PIXELS, ~89 MP).
MAX_AVATAR_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_AVATAR_PIXELS = 16_000_000
# Längste Kante der gespeicherten Fassung: Größer zeigt weder das Verzeichnis
# noch der Zuschnitt-Dialog etwas an, es kostet nur Platz und Bandbreite.
# Die Zuschnittwerte (Position, Skalierung) sind relativ und bleiben gültig.
MAX_AVATAR_EDGE = 2048
# Nicht-Metadaten aus image.info, die beim Speichern erhalten bleiben müssen:
# Ohne "transparency" verlöre eine Palette-PNG ihren transparenten Hintergrund.
_PRESERVED_IMAGE_INFO = ("transparency",)

_DEFAULT_INVALID_IMAGE_MESSAGE = (
    "Не удалось обработать изображение. Загрузи другой файл в формате "
    "JPG, PNG или WebP."
)
UNSUPPORTED_FORMAT_MESSAGE = "Поддерживаются только JPEG, PNG и WebP."
_TOO_LARGE_IMAGE_MESSAGE = (
    "Изображение слишком большое. Загрузи фото поменьше – "
    f"не больше {MAX_AVATAR_PIXELS // 1_000_000} мегапикселей."
)


# Was Pillow beim Lesen kaputter oder manipulierter Dateien wirft – außer
# OSError (abgeschnittene Daten) auch Parserfehler der Plugins. Ohne die
# vollständige Liste würde eine präparierte Datei zu einem 500 statt 400.
IMAGE_DECODE_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    ValueError,
    EOFError,
    IndexError,
    SyntaxError,
    struct.error,
    Image.DecompressionBombError,
    Image.DecompressionBombWarning,
)


class InvalidAvatarImage(ValueError):
    """
    Die hochgeladene Datei lässt sich nicht als Bild neu schreiben.

    user_message ist der Text für das Mitglied (russisch), str(exc) der
    technische Grund fürs Log.
    """

    def __init__(
        self, reason: str, *, user_message: str = _DEFAULT_INVALID_IMAGE_MESSAGE
    ):
        super().__init__(reason)
        self.user_message = user_message


def has_allowed_image_signature(head: bytes) -> bool:
    """
    Beginnen die Bytes wie ein JPEG, PNG oder WebP?

    Für die Vorprüfung, bevor irgendein Bildparser die Datei sieht – head
    sind die ersten SIGNATURE_PROBE_BYTES Bytes.
    """
    return (
        head.startswith(_JPEG_SIGNATURE)
        or head.startswith(_PNG_SIGNATURE)
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


def is_private_media_path(path: str) -> bool:
    """
    Gehört der Pfad unter /media/ zu den nicht öffentlichen Originalen?

    normpath wie in django.views.static.serve: Sonst käme man über
    "avatars/./originals/…" oder "avatars//originals/…" an der Prüfung vorbei
    und trotzdem bei derselben Datei an.
    """
    normalized = posixpath.normpath(path).lstrip("/")
    return normalized == AVATAR_ORIGINALS_DIR or normalized.startswith(
        f"{AVATAR_ORIGINALS_DIR}/"
    )


def is_legacy_avatar_path(name: str) -> bool:
    """
    Trägt der Pfad noch das alte, aus der User-ID ableitbare Namensschema?

    normpath aus demselben Grund wie in is_private_media_path.
    """
    directory, _, file_name = posixpath.normpath(name).lstrip("/").rpartition("/")
    return directory in (AVATAR_DIR, AVATAR_ORIGINALS_DIR) and bool(
        _LEGACY_FILE_NAME.match(file_name)
    )


def is_legacy_avatar_file_name(file_name: str) -> bool:
    return bool(_LEGACY_FILE_NAME.match(file_name))


def strip_image_metadata(upload) -> ContentFile:
    """
    Schreibt das Bild ohne EXIF/XMP/Kommentare neu.

    EXIF enthält bei Handyfotos oft GPS-Koordinaten, Gerät und Aufnahmezeit –
    bei einem öffentlich abrufbaren Avatar ein unnötiges Datenleck. Die
    Ausrichtung wird vorher eingerechnet, sonst stünde ein Hochkantfoto ohne
    das Orientation-Tag auf der Seite. Das ICC-Farbprofil bleibt (keine
    personenbezogenen Daten, ohne es kippen die Farben). Bilder mit längerer
    Kante als MAX_AVATAR_EDGE werden verkleinert.
    """
    upload.seek(0)
    # DecompressionBombWarning als Fehler: Pillow würde ein Bild über
    # MAX_IMAGE_PIXELS sonst nur mit Warnung öffnen und weiterdekodieren.
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            image, source_format, icc_profile = _decode(upload)
        except InvalidAvatarImage:
            # Eigene Meldung (z. B. zu viele Pixel) – nicht als ValueError
            # unten in die Standardmeldung umschreiben.
            raise
        except UnidentifiedImageError as exc:
            # Vor IMAGE_DECODE_ERRORS: UnidentifiedImageError ist ein OSError,
            # bekommt aber die genauere Meldung (Format nicht erlaubt).
            raise InvalidAvatarImage(
                str(exc), user_message=UNSUPPORTED_FORMAT_MESSAGE
            ) from exc
        except IMAGE_DECODE_ERRORS as exc:
            raise InvalidAvatarImage(str(exc)) from exc

    # Pillow übernimmt beim Speichern Teile von image.info (je nach Format
    # u. a. XMP und EXIF) – deshalb leeren und nur behalten, was kein
    # Metadatum ist. Das ICC-Profil geht unten explizit mit.
    image.info = {
        key: image.info[key] for key in _PRESERVED_IMAGE_INFO if key in image.info
    }

    save_options: dict = {}
    if icc_profile:
        save_options["icc_profile"] = icc_profile
    if source_format == "JPEG":
        save_options["quality"] = _JPEG_QUALITY
        if image.mode not in ("RGB", "L", "CMYK"):
            image = image.convert("RGB")
    elif source_format == "WEBP":
        save_options["quality"] = _WEBP_QUALITY

    buffer = io.BytesIO()
    try:
        image.save(buffer, format=source_format, **save_options)
    except IMAGE_DECODE_ERRORS as exc:
        raise InvalidAvatarImage(str(exc)) from exc
    return ContentFile(
        buffer.getvalue(), name=f"avatar.{_EXTENSION_BY_FORMAT[source_format]}"
    )


def _decode(upload) -> tuple[Image.Image, str, bytes | None]:
    """
    Dekodiert das Bild ausgerichtet und auf MAX_AVATAR_EDGE verkleinert.

    Gibt Bild, Quellformat und ICC-Profil zurück; Pillow-Fehler gehen
    ungefiltert an strip_image_metadata.
    """
    with Image.open(upload, formats=ALLOWED_AVATAR_FORMATS) as source:
        _ensure_acceptable_pixel_count(source)
        source_format = source.format
        icc_profile = source.info.get("icc_profile")
        if source_format == "JPEG":
            # libjpeg dekodiert dann gleich in 1/2, 1/4 oder 1/8 der Größe,
            # solange beide Kanten mindestens MAX_AVATAR_EDGE bleiben – spart
            # Speicher, bevor exif_transpose das ganze Bild lädt. Die Box ist
            # quadratisch, die Wahl hängt also nicht von der Ausrichtung ab;
            # das Seitenverhältnis bleibt, das Orientation-Tag wendet
            # exif_transpose danach wie gehabt an. Mit MAX_AVATAR_PIXELS =
            # 16 MP greift das noch nicht (Faktor 2 braucht zwei Kanten
            # ≥ 4096, also > 16 MP) – es wirkt erst, wenn die Pixelgrenze
            # steigt, und kostet bis dahin nichts.
            source.draft("RGB", (MAX_AVATAR_EDGE, MAX_AVATAR_EDGE))
        image = ImageOps.exif_transpose(source)
        image.load()
    image.thumbnail((MAX_AVATAR_EDGE, MAX_AVATAR_EDGE))
    return image, source_format, icc_profile


def _ensure_acceptable_pixel_count(image: Image.Image) -> None:
    """
    Prüft die Pixelzahl aus dem Header, bevor das Bild dekodiert wird.
    """
    width, height = image.size
    if width * height > MAX_AVATAR_PIXELS:
        raise InvalidAvatarImage(
            f"Bild hat {width}x{height} Pixel, erlaubt sind {MAX_AVATAR_PIXELS}.",
            user_message=_TOO_LARGE_IMAGE_MESSAGE,
        )


def delete_avatar_files(names: Iterable[str]) -> None:
    """
    Löscht die Dateien, ein einzelner Fehlschlag hält die übrigen nicht auf.

    Eine verwaiste Datei ist ärgerlich, aber kein Grund, den Request oder die
    Kontolöschung scheitern zu lassen – sie gehört ins Log.
    """
    for name in sorted(names):
        try:
            default_storage.delete(name)
        except OSError as exc:
            logger.warning("Avatar-Datei %s nicht löschbar: %s", name, exc)


def schedule_avatar_file_deletion(names: Iterable[str]) -> None:
    """
    Löscht die Dateien erst nach dem Commit der laufenden Transaktion.

    Vorher verweist die Datenbank noch auf sie: Ein Rollback ließe sonst ein
    Profil mit fehlender Datei zurück, und ein Worker, der das Profil gerade
    gelesen hat, fände die Datei nicht mehr.
    """
    pending = frozenset(names)
    if pending:
        transaction.on_commit(partial(delete_avatar_files, pending))
