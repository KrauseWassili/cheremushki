"""
Ablage, Bereinigung und Aufräumen der Avatar-Dateien.

Eigenes Modul ohne Modellimport: models.py braucht die Pfadkonstanten und die
Aufräumfunktionen für anonymize(), ein Import in die Gegenrichtung wäre
zirkulär.
"""

import io
import logging
import posixpath
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

# Pillow-Format → Dateiendung. Andere Formate (GIF, BMP, …) liest Pillow zwar,
# sie werden aber als JPEG neu geschrieben: upload_to lässt ohnehin nur diese
# Endungen zu, und Endung und Inhalt sollen zusammenpassen.
_EXTENSION_BY_FORMAT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
_FALLBACK_FORMAT = "JPEG"
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
_TOO_LARGE_IMAGE_MESSAGE = (
    "Изображение слишком большое. Загрузи фото поменьше – "
    f"не больше {MAX_AVATAR_PIXELS // 1_000_000} мегапикселей."
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
            with Image.open(upload) as source:
                _ensure_acceptable_pixel_count(source)
                source_format = source.format
                icc_profile = source.info.get("icc_profile")
                image = ImageOps.exif_transpose(source)
                image.load()
        except (
            OSError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise InvalidAvatarImage(str(exc)) from exc

    image.thumbnail((MAX_AVATAR_EDGE, MAX_AVATAR_EDGE))
    # Pillow übernimmt beim Speichern Teile von image.info (je nach Format
    # u. a. XMP und EXIF) – deshalb leeren und nur behalten, was kein
    # Metadatum ist. Das ICC-Profil geht unten explizit mit.
    image.info = {
        key: image.info[key] for key in _PRESERVED_IMAGE_INFO if key in image.info
    }

    target_format = (
        source_format if source_format in _EXTENSION_BY_FORMAT else _FALLBACK_FORMAT
    )
    save_options: dict = {}
    if icc_profile:
        save_options["icc_profile"] = icc_profile
    if target_format == "JPEG":
        save_options["quality"] = _JPEG_QUALITY
        if image.mode not in ("RGB", "L", "CMYK"):
            image = image.convert("RGB")
    elif target_format == "WEBP":
        save_options["quality"] = _WEBP_QUALITY

    buffer = io.BytesIO()
    try:
        image.save(buffer, format=target_format, **save_options)
    except (OSError, ValueError) as exc:
        raise InvalidAvatarImage(str(exc)) from exc
    return ContentFile(
        buffer.getvalue(), name=f"avatar.{_EXTENSION_BY_FORMAT[target_format]}"
    )


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
