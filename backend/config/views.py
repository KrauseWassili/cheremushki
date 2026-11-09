"""
Infrastruktur-Views außerhalb der fachlichen /api/v1-Routen.
"""

from django.http import Http404, HttpRequest, HttpResponse
from django.views.static import serve

from apps.profiles.avatar_files import is_private_media_path


def healthz(request: HttpRequest) -> HttpResponse:
    """
    Lebenszeichen für den Docker-Healthcheck.

    Bewusst ohne Datenbank- oder Redis-Zugriff: Ein Healthcheck, der an einer
    Abhängigkeit hängt, markiert bei einem Postgres-Neustart auch den
    Webprozess als krank – der ist aber gesund und erholt sich von selbst.
    Geprüft wird nur, dass daphne Requests annimmt und Django antwortet.
    """
    return HttpResponse("ok", content_type="text/plain")


def public_media(request: HttpRequest, path: str, document_root: str) -> HttpResponse:
    """
    Liefert MEDIA_ROOT aus – ohne die Avatar-Originale.

    Die Originale zeigen mehr als der Zuschnitt, den das Mitglied fürs
    Verzeichnis gewählt hat; der Eigentümer bekommt sie authentifiziert über
    /api/v1/profiles/user/me/avatar/original/.
    """
    if is_private_media_path(path):
        raise Http404
    return serve(request, path, document_root=document_root)
