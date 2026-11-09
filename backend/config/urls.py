import re

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.accounts.routers import router as account_router
from apps.bot.routers import router as tg_router
from apps.profiles.routers import router as profiles_router
from config.views import healthz, public_media

urlpatterns = [
    # Ohne Auth und Throttle: Docker fragt alle paar Sekunden an, ein
    # Rate-Limit würde den Container nach kurzer Zeit als krank melden.
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/accounts/", include(account_router.urls)),
    path("api/v1/profiles/", include(profiles_router.urls)),
    path("api/v1/bot/", include(tg_router.urls)),
]

# Bewusst unabhängig von DEBUG: Der geteilte Nginx (stock_scanner_app) leitet
# /media/ nur an diesen Container weiter, liefert selbst nichts aus – ohne
# diese Route wäre bei DEBUG=False jeder Avatar 404. public_media streamt
# asynchron, hat aber wie Djangos static.serve keine Range-Logik; für eine
# kleine Community mit nur Avataren in MEDIA_ROOT ist das tragbar. Sobald der
# Nginx Zugriff auf das Media-Volume bekommt, dort ausliefern und diese Route
# auf DEBUG zurücknehmen. django.conf.urls.static.static() ist hier
# unbrauchbar, weil es bei DEBUG=False eine leere Liste liefert.
#
# public_media statt serve: Die Avatar-Originale (avatars/originals/) und
# Altlasten (avatars/user-<id>…) sind nicht öffentlich, und serve() würde
# unter ASGI jede Datei vorab komplett in den Speicher lesen. re.escape wie in
# django.conf.urls.static – ein Punkt o. Ä. in MEDIA_URL wäre sonst ein
# Regex-Platzhalter.
urlpatterns += [
    re_path(
        r"^%s(?P<path>.*)$" % re.escape(settings.MEDIA_URL.lstrip("/")),
        public_media,
        {"document_root": settings.MEDIA_ROOT},
    ),
]

if settings.API_DOCS_ENABLED:
    urlpatterns += [
        path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/v1/schema/swagger/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/v1/schema/redoc/",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
