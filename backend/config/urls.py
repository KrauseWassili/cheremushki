from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.accounts.routers import router as account_router
from apps.bot.routers import router as tg_router
from apps.profiles.routers import router as profiles_router

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/accounts/", include(account_router.urls)),
    path("api/v1/profiles/", include(profiles_router.urls)),
    path("api/v1/bot/", include(tg_router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

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
