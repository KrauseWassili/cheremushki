"""
Infrastruktur-Views außerhalb der fachlichen /api/v1-Routen.
"""

import mimetypes
import os
import posixpath
from pathlib import Path
from stat import S_ISREG
from typing import BinaryIO

from asgiref.sync import sync_to_async
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    HttpResponseNotModified,
)
from django.utils._os import safe_join
from django.utils.http import http_date
from django.views.static import was_modified_since

from apps.profiles.avatar_files import is_legacy_avatar_path, is_private_media_path
from apps.profiles.file_streaming import streaming_file_response

DEFAULT_MEDIA_CONTENT_TYPE = "application/octet-stream"


def healthz(request: HttpRequest) -> HttpResponse:
    """
    Lebenszeichen für den Docker-Healthcheck.

    Bewusst ohne Datenbank- oder Redis-Zugriff: Ein Healthcheck, der an einer
    Abhängigkeit hängt, markiert bei einem Postgres-Neustart auch den
    Webprozess als krank – der ist aber gesund und erholt sich von selbst.
    Geprüft wird nur, dass daphne Requests annimmt und Django antwortet.
    """
    return HttpResponse("ok", content_type="text/plain")


async def public_media(
    request: HttpRequest, path: str, document_root: str
) -> HttpResponseBase:
    """
    Liefert MEDIA_ROOT aus – ohne die Avatar-Originale und ohne Altlasten.

    Die Originale zeigen mehr als der Zuschnitt, den das Mitglied fürs
    Verzeichnis gewählt hat; der Eigentümer bekommt sie authentifiziert über
    /api/v1/profiles/user/me/avatar/original/. Avatare im alten Schema
    avatars/user-<id>… sind per Durchzählen der User-ID erratbar und tragen
    noch alte EXIF-Daten – cleanup_legacy_avatars verschiebt sie, diese
    Sperre greift zusätzlich, falls dabei etwas liegen geblieben ist.

    Nachbau von django.views.static.serve (Pfadprüfung, If-Modified-Since,
    Last-Modified, Content-Encoding) mit gestreamter Antwort: serve() gibt
    eine FileResponse mit der Datei selbst zurück, die Django unter ASGI vor
    dem Senden komplett in den Speicher liest. Den nosniff-Header setzt
    SecurityMiddleware für alle Antworten.
    """
    normalized = posixpath.normpath(path).lstrip("/")
    if is_private_media_path(normalized) or is_legacy_avatar_path(normalized):
        raise Http404
    # safe_join wirft bei Pfaden außerhalb von document_root
    # SuspiciousFileOperation – Django antwortet darauf mit 400.
    full_path = Path(safe_join(document_root, normalized))
    opened = await sync_to_async(_open_regular_file, thread_sensitive=False)(full_path)
    if opened is None:
        raise Http404
    handle, stat = opened
    if not was_modified_since(
        request.META.get("HTTP_IF_MODIFIED_SINCE"), stat.st_mtime
    ):
        await sync_to_async(handle.close, thread_sensitive=False)()
        return HttpResponseNotModified()
    content_type, encoding = mimetypes.guess_type(str(full_path))
    response = streaming_file_response(
        handle,
        size=stat.st_size,
        content_type=content_type or DEFAULT_MEDIA_CONTENT_TYPE,
    )
    response["Last-Modified"] = http_date(stat.st_mtime)
    if encoding:
        response["Content-Encoding"] = encoding
    return response


def _open_regular_file(full_path: Path) -> tuple[BinaryIO, os.stat_result] | None:
    """
    Öffnet eine reguläre Datei; None für Verzeichnisse und Fehlendes.

    stat über das geöffnete Handle: Größe und Datum gehören dann sicher zu
    der Datei, die gestreamt wird, auch wenn sie dazwischen ersetzt wird.
    """
    try:
        handle = full_path.open("rb")
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        return None
    stat = os.fstat(handle.fileno())
    if not S_ISREG(stat.st_mode):
        handle.close()
        return None
    return handle, stat
