import re
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver
from django.utils import translation
from rest_framework.test import APIClient

from config.middleware import admin_language_middleware
from config.views import public_media

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "config-tests",
    }
}


class EnvExampleTests(SimpleTestCase):
    # --- env("X") ohne Default fehlt der Wert, startet die Anwendung nicht.
    REQUIRED_RE = re.compile(r'env\("([A-Z_]+)"\)')
    # --- Jede Form von env(...)-Zugriff, auch mit Default.
    ANY_RE = re.compile(r'env(?:\.\w+)?\(\s*"([A-Z_]+)"')
    DOCUMENTED_RE = re.compile(r"^([A-Z_]+)=", re.MULTILINE)
    # --- Next.js liest Laufzeit-/Build-Env über process.env.NAME.
    FRONTEND_ENV_RE = re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)")
    # --- docker compose interpoliert ${NAME} bzw. ${NAME:-default} aus .env
    # (z. B. PUBLISH_IP); $${NAME} ist escaped und wird erst im Container
    # gelesen, zählt also nicht.
    COMPOSE_ENV_RE = re.compile(r"(?<!\$)\$\{([A-Z][A-Z0-9_]*)")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        backend_dir = Path(__file__).resolve().parent.parent
        repo_root = backend_dir.parent
        cls.settings_source = (backend_dir / "config" / "settings.py").read_text()
        cls.example = (repo_root / ".env.example").read_text()
        cls.compose_source = (repo_root / "docker-compose.yml").read_text()
        frontend_src = repo_root / "frontend" / "src"
        cls.frontend_source = "\n".join(
            path.read_text()
            for path in frontend_src.rglob("*")
            if path.suffix in {".ts", ".tsx", ".js", ".mjs"}
        )

    def documented(self) -> set[str]:
        return set(self.DOCUMENTED_RE.findall(self.example))

    def read_by_apps(self) -> set[str]:
        return (
            set(self.ANY_RE.findall(self.settings_source))
            | set(self.FRONTEND_ENV_RE.findall(self.frontend_source))
            | set(self.COMPOSE_ENV_RE.findall(self.compose_source))
        )

    def test_every_required_variable_is_documented(self):
        required = set(self.REQUIRED_RE.findall(self.settings_source))
        self.assertGreater(len(required), 5, "Regex findet keine env()-Aufrufe mehr")
        self.assertEqual(
            required - self.documented(),
            set(),
            "Diese Pflichtvariablen fehlen in .env.example – ein frischer "
            "Clone startet damit nicht.",
        )

    def test_no_variable_documented_that_nobody_reads(self):
        self.assertTrue(
            self.frontend_source,
            "frontend/src ist leer oder nicht lesbar – Frontend-Env würde "
            "fälschlich als ungelesen gelten.",
        )
        self.assertEqual(
            self.documented() - self.read_by_apps(),
            set(),
            "Diese Variablen stehen in .env.example, werden aber weder von "
            "Django noch vom Frontend noch von docker-compose.yml gelesen.",
        )


class AdminLanguageMiddlewareUnitTests(SimpleTestCase):
    """
    Die Middleware selbst, sync und async: Admin-Pfade laufen unter "de",
    alles andere unter LANGUAGE_CODE ("ru").
    """

    def setUp(self):
        self.factory = RequestFactory()

    @staticmethod
    def language_recording_view(seen: list):
        def view(request):
            seen.append(translation.get_language())
            return HttpResponse()

        return view

    @staticmethod
    def async_language_recording_view(seen: list):
        async def view(request):
            seen.append(translation.get_language())
            return HttpResponse()

        return view

    def test_middleware_sync_admin_path_uses_german(self):
        seen = []
        middleware = admin_language_middleware(self.language_recording_view(seen))
        middleware(self.factory.get("/admin/login/"))
        self.assertEqual(seen, ["de"])

    def test_middleware_sync_api_path_keeps_default_language(self):
        seen = []
        middleware = admin_language_middleware(self.language_recording_view(seen))
        middleware(self.factory.get("/api/v1/accounts/user/me/"))
        self.assertEqual(seen, [settings.LANGUAGE_CODE])

    def test_middleware_sync_restores_language_after_admin_request(self):
        middleware = admin_language_middleware(self.language_recording_view([]))
        middleware(self.factory.get("/admin/"))
        self.assertEqual(translation.get_language(), settings.LANGUAGE_CODE)

    def test_middleware_similar_prefix_is_not_admin(self):
        # "/administration" beginnt nicht mit "/admin/".
        seen = []
        middleware = admin_language_middleware(self.language_recording_view(seen))
        middleware(self.factory.get("/administration/"))
        self.assertEqual(seen, [settings.LANGUAGE_CODE])

    async def test_middleware_async_admin_path_uses_german(self):
        seen = []
        middleware = admin_language_middleware(self.async_language_recording_view(seen))
        await middleware(self.factory.get("/admin/login/"))
        self.assertEqual(seen, ["de"])

    async def test_middleware_async_api_path_keeps_default_language(self):
        seen = []
        middleware = admin_language_middleware(self.async_language_recording_view(seen))
        await middleware(self.factory.get("/api/v1/profiles/"))
        self.assertEqual(seen, [settings.LANGUAGE_CODE])
        self.assertEqual(translation.get_language(), settings.LANGUAGE_CODE)


@override_settings(CACHES=LOCMEM_CACHE)
class AreaLanguageIntegrationTests(TestCase):
    """
    Durch den echten Middleware-Stack: Admin deutsch, API-Fehler russisch –
    unabhängig vom Accept-Language des Browsers.
    """

    API_ME = "/api/v1/accounts/user/me/"

    def assert_admin_login_german(self, response):
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('lang="de"', content)
        self.assertIn("Anmelden", content)

    def assert_unauthenticated_detail_russian(self, response):
        self.assertEqual(response.status_code, 401)
        # Projektkatalog (backend/locale) statt DRFs förmlichem
        # "Учетные данные не были предоставлены.".
        self.assertEqual(response.json()["detail"], "Сначала войди в аккаунт.")

    def test_admin_login_page_is_german(self):
        self.assert_admin_login_german(
            self.client.get("/admin/login/", HTTP_ACCEPT_LANGUAGE="ru")
        )

    def test_api_unauthenticated_error_is_russian(self):
        self.assert_unauthenticated_detail_russian(
            APIClient().get(self.API_ME, HTTP_ACCEPT_LANGUAGE="de")
        )

    def test_api_validation_error_is_russian(self):
        response = APIClient().post(
            "/api/v1/accounts/sign-up/", {}, format="json", HTTP_ACCEPT_LANGUAGE="de"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Обязательное поле", str(response.data["email"][0]))

    def test_api_after_admin_request_stays_russian(self):
        self.client.get("/admin/login/")
        self.assert_unauthenticated_detail_russian(self.client.get(self.API_ME))

    async def test_admin_login_page_is_german_async(self):
        self.assert_admin_login_german(
            await self.async_client.get("/admin/login/", ACCEPT_LANGUAGE="ru")
        )

    async def test_api_unauthenticated_error_is_russian_async(self):
        self.assert_unauthenticated_detail_russian(
            await self.async_client.get(self.API_ME, ACCEPT_LANGUAGE="de")
        )


def media_route():
    for pattern in get_resolver().url_patterns:
        if getattr(pattern, "callback", None) is public_media:
            return pattern
    raise AssertionError("Keine Media-Route in config.urls")


class MediaRouteConfigurationTests(SimpleTestCase):
    def test_media_route_serves_from_media_root_without_indexes(self):
        route = media_route()
        self.assertEqual(
            Path(route.default_args["document_root"]), Path(settings.MEDIA_ROOT)
        )
        self.assertFalse(route.default_args.get("show_indexes", False))


@override_settings(DEBUG=False)
class MediaRouteTests(SimpleTestCase):
    """
    /media/ wird auch bei DEBUG=False ausgeliefert (der Nginx reicht nur
    weiter). Die Route bindet MEDIA_ROOT beim Import, daher wird hier ihr
    document_root auf ein Temp-Verzeichnis umgebogen; daneben liegt eine
    "geheime" Datei, die nie erreichbar sein darf.
    """

    SECRET = b"SECRET_KEY=nicht-ausliefern"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        outer = Path(tmp.name)
        self.media_root = outer / "media"
        (self.media_root / "avatars").mkdir(parents=True)
        (self.media_root / "avatars" / "anna.png").write_bytes(b"\x89PNG-test")
        (self.media_root / "avatars" / "originals").mkdir()
        (self.media_root / "avatars" / "originals" / "anna.png").write_bytes(
            b"\x89PNG-original"
        )
        (outer / "settings.py").write_bytes(self.SECRET)

        patcher = mock.patch.dict(
            media_route().default_args, {"document_root": str(self.media_root)}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, path: str):
        response = self.client.get(path)
        self.addCleanup(response.close)
        return response

    def body(self, response) -> bytes:
        if response.streaming:
            return b"".join(response.streaming_content)
        return response.content

    def test_media_existing_file_is_served_without_debug(self):
        response = self.get("/media/avatars/anna.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(response), b"\x89PNG-test")
        self.assertEqual(response["Content-Type"], "image/png")

    def test_media_missing_file_is_404(self):
        self.assertEqual(self.get("/media/avatars/fehlt.png").status_code, 404)

    def test_media_directory_listing_is_404(self):
        for path in ("/media/", "/media/avatars/", "/media/avatars"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 404)

    def test_media_path_traversal_is_rejected(self):
        # safe_join wirft SuspiciousFileOperation -> Django antwortet 400;
        # 404 wäre ebenso in Ordnung. Entscheidend: die Datei kommt nicht raus.
        for path in (
            "/media/../settings.py",
            "/media/avatars/../../settings.py",
            "/media/%2e%2e/settings.py",
            "/media/..%2fsettings.py",
            "/media/%2e%2e%2fsettings.py",
        ):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertIn(response.status_code, (400, 404))
                self.assertNotIn(self.SECRET, self.body(response))

    def test_avatar_originals_are_never_served(self):
        """
        Das Original zeigt mehr als der gewählte Zuschnitt – es gibt es nur
        über die authentifizierte API, auch nicht über Pfad-Varianten.
        """
        for path in (
            "/media/avatars/originals/anna.png",
            "/media/avatars/./originals/anna.png",
            "/media/avatars//originals/anna.png",
            "/media/avatars/originals/",
        ):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b"PNG-original", self.body(response))


class HealthzTests(SimpleTestCase):
    def test_healthz_answers_without_database(self):
        # SimpleTestCase verbietet DB-Zugriffe – ein Query hier ließe den
        # Test scheitern.
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
