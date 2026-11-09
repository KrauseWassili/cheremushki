import importlib.util
import os
import re
import tempfile
from pathlib import Path
from unittest import mock

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.checks import run_checks
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver
from django.utils import translation
from rest_framework.test import APIClient

from config.checks import check_secret_key
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


async def collect_async_stream(response) -> bytes:
    return b"".join([chunk async for chunk in response.streaming_content])


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
    LEGACY = b"\xff\xd8\xff-altlast-mit-exif"
    CURRENT = b"\xff\xd8\xff-aktueller-avatar"
    # 2023-11-14 22:13:20 UTC – feste mtime statt echter Uhrzeit.
    MTIME = 1_700_000_000
    MTIME_HTTP = "Tue, 14 Nov 2023 22:13:20 GMT"

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
        # Altlasten im alten, per User-ID erratbaren Schema.
        for legacy in (
            "avatars/user-1.jpg",
            "avatars/user-1_AbC.jpg",
            "avatars/originals/user-1.jpg",
        ):
            (self.media_root / legacy).write_bytes(self.LEGACY)
        self.current = self.media_root / "avatars" / f"{'a' * 32}.jpg"
        self.current.write_bytes(self.CURRENT)
        os.utime(self.current, (self.MTIME, self.MTIME))

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
        if not response.streaming:
            return response.content
        if response.is_async:
            return async_to_sync(collect_async_stream)(response)
        return b"".join(response.streaming_content)

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

    def test_media_legacy_avatar_names_are_never_served(self):
        for path in (
            "/media/avatars/user-1.jpg",
            "/media/avatars/user-1_AbC.jpg",
            "/media/avatars/originals/user-1.jpg",
            "/media/avatars/./user-1.jpg",
            "/media/avatars//user-1.jpg",
        ):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b"altlast", self.body(response))

    def test_media_current_avatar_is_streamed_with_cache_headers(self):
        response = self.get(f"/media/avatars/{'a' * 32}.jpg")

        self.assertEqual(response.status_code, 200)
        # Async-Iterator statt Datei: unter ASGI blockweise gestreamt.
        self.assertTrue(response.streaming)
        self.assertTrue(response.is_async)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(response["Content-Length"], str(len(self.CURRENT)))
        self.assertEqual(response["Last-Modified"], self.MTIME_HTTP)
        self.assertEqual(self.body(response), self.CURRENT)

    def test_media_if_modified_since_unchanged_returns_304(self):
        response = self.client.get(
            f"/media/avatars/{'a' * 32}.jpg", HTTP_IF_MODIFIED_SINCE=self.MTIME_HTTP
        )
        self.addCleanup(response.close)

        self.assertEqual(response.status_code, 304)
        self.assertEqual(response.content, b"")

    def test_media_if_modified_since_older_returns_200(self):
        response = self.client.get(
            f"/media/avatars/{'a' * 32}.jpg",
            HTTP_IF_MODIFIED_SINCE="Mon, 13 Nov 2023 00:00:00 GMT",
        )
        self.addCleanup(response.close)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(response), self.CURRENT)

    def test_media_subdirectory_is_404(self):
        for path in ("/media/avatars/originals", "/media/avatars/."):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 404)


# Zufallswert, 64 Zeichen, ohne Platzhalter-Teilstrings.
STRONG_SECRET_KEY = "q7Vf2LpX9sRk4TnB8wZc1HyJ6mQd3GaE5uYo0iKbNlPrStUvWxZaBcDeFgHjKmNp"


class SecretKeyCheckTests(SimpleTestCase):
    @staticmethod
    def config_error_ids(messages) -> list[str]:
        return [m.id for m in messages if m.id and m.id.startswith("config.")]

    def test_secret_key_check_rejects_weak_values_without_debug(self):
        for value in (
            "TODO_SET_ME",
            "kurz",
            "a" * 49,
            "django-insecure-" + "x" * 50,
            "changeme-" + "x" * 50,
            "  secret  ",
        ):
            with self.subTest(value=value):
                with override_settings(DEBUG=False, SECRET_KEY=value):
                    self.assertEqual(
                        self.config_error_ids(check_secret_key(None)), ["config.E001"]
                    )

    @override_settings(DEBUG=True, SECRET_KEY="TODO_SET_ME")
    def test_secret_key_check_is_silent_with_debug(self):
        self.assertEqual(check_secret_key(None), [])

    @override_settings(DEBUG=False, SECRET_KEY=STRONG_SECRET_KEY)
    def test_secret_key_check_accepts_strong_value(self):
        self.assertEqual(check_secret_key(None), [])

    @override_settings(DEBUG=False, SECRET_KEY="a" * 50)
    def test_secret_key_check_accepts_exactly_min_length(self):
        # MIN_SECRET_KEY_LENGTH = 50, Grenze inklusive.
        self.assertEqual(check_secret_key(None), [])

    @override_settings(DEBUG=False, SECRET_KEY="TODO_SET_ME")
    def test_secret_key_check_runs_only_as_deploy_check(self):
        self.assertEqual(
            self.config_error_ids(run_checks(include_deployment_checks=False)), []
        )
        self.assertEqual(
            self.config_error_ids(run_checks(include_deployment_checks=True)),
            ["config.E001"],
        )


def load_settings_with_debug(debug: str):
    """
    Führt config/settings.py als eigenes Modul mit gesetztem DEBUG aus.

    SESSION_/CSRF_COOKIE_SECURE werden beim Import aus DEBUG abgeleitet;
    override_settings(DEBUG=…) ändert sie nicht. Das Modul landet nicht in
    sys.modules und berührt django.conf.settings nicht. os.environ hat
    Vorrang vor der .env (read_env überschreibt nicht).
    """
    spec = importlib.util.spec_from_file_location(
        f"config._settings_probe_{debug.lower()}",
        Path(__file__).resolve().parent / "settings.py",
    )
    module = importlib.util.module_from_spec(spec)
    env = {
        "DEBUG": debug,
        # Ohne Cache-URL bricht settings.py mit DEBUG=False ab; verbunden
        # wird hier nicht.
        "DJANGO_CACHE_URL": "redis://cache.invalid:6379/0",
    }
    with mock.patch.dict(os.environ, env):
        spec.loader.exec_module(module)
    return module


class SecureCookieSettingsTests(SimpleTestCase):
    def test_cookies_are_secure_without_debug(self):
        module = load_settings_with_debug("False")
        self.assertFalse(module.DEBUG)
        self.assertTrue(module.SESSION_COOKIE_SECURE)
        self.assertTrue(module.CSRF_COOKIE_SECURE)

    def test_cookies_are_not_secure_with_debug(self):
        # Dev-Stack läuft über http – Secure-Cookies würden den Admin-Login
        # dort unmöglich machen.
        module = load_settings_with_debug("True")
        self.assertTrue(module.DEBUG)
        self.assertFalse(module.SESSION_COOKIE_SECURE)
        self.assertFalse(module.CSRF_COOKIE_SECURE)


class HealthzTests(SimpleTestCase):
    def test_healthz_answers_without_database(self):
        # SimpleTestCase verbietet DB-Zugriffe – ein Query hier ließe den
        # Test scheitern.
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
