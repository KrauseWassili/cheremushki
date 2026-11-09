"""
Sprachwahl pro Bereich: API und Mails russisch (LANGUAGE_CODE), Admin deutsch.

Bewusst kein LocaleMiddleware: Das würde die Sprache aus Accept-Language
ableiten, die Oberfläche ist aber unabhängig vom Browser russisch und der
Admin unabhängig vom Browser deutsch.
"""

from asgiref.sync import iscoroutinefunction
from django.http import HttpRequest, HttpResponse
from django.utils import translation
from django.utils.decorators import sync_and_async_middleware

ADMIN_LANGUAGE = "de"
ADMIN_PATH_PREFIX = "/admin/"


def _is_admin_request(request: HttpRequest) -> bool:
    return request.path_info.startswith(ADMIN_PATH_PREFIX)


# Sync und async: Unter daphne (ASGI) würde eine reine Sync-Middleware jeden
# Request – auch die adrf-Views – über einen zusätzlichen Thread-Wechsel leiten.
@sync_and_async_middleware
def admin_language_middleware(get_response):
    if iscoroutinefunction(get_response):

        async def middleware(request: HttpRequest) -> HttpResponse:
            if not _is_admin_request(request):
                return await get_response(request)
            with translation.override(ADMIN_LANGUAGE):
                return await get_response(request)

    else:

        def middleware(request: HttpRequest) -> HttpResponse:
            if not _is_admin_request(request):
                return get_response(request)
            with translation.override(ADMIN_LANGUAGE):
                return get_response(request)

    return middleware
