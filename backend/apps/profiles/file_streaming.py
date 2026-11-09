"""
Dateiauslieferung unter ASGI, ohne die Datei vorher komplett zu lesen.

Gemeinsam für den Original-Endpunkt (apps.profiles.views) und /media/
(config.views.public_media). Eine FileResponse mit der Datei selbst liest
Django unter ASGI per sync_to_async(list) komplett in den Speicher – bei
parallelen Abrufen addiert sich das. Deshalb ein Async-Iterator, der
blockweise im Thread liest.
"""

from collections.abc import AsyncIterator
from typing import BinaryIO

from asgiref.sync import sync_to_async
from django.http import FileResponse


def streaming_file_response(
    handle: BinaryIO, *, size: int, content_type: str
) -> FileResponse:
    """
    Antwort, die die bereits geöffnete Datei streamt und danach schließt.
    """
    response = FileResponse(_aiter_file_chunks(handle), content_type=content_type)
    # Beim Async-Iterator kennt FileResponse die Größe nicht selbst.
    response["Content-Length"] = str(size)
    return response


async def _aiter_file_chunks(handle: BinaryIO) -> AsyncIterator[bytes]:
    """
    Liest die geöffnete Datei blockweise im Thread und schließt sie danach.

    thread_sensitive=False: Ein Dateizugriff braucht weder den
    Request-Thread noch die DB-Verbindung. Mit dem Default liefen alle
    Blöcke aller gleichzeitigen Downloads nacheinander durch den einen
    geteilten Sync-Thread und blockierten dort auch ORM-Aufrufe.
    """
    try:
        while chunk := await sync_to_async(handle.read, thread_sensitive=False)(
            FileResponse.block_size
        ):
            yield chunk
    finally:
        await sync_to_async(handle.close, thread_sensitive=False)()
