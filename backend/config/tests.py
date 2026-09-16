import re
from pathlib import Path

from django.test import SimpleTestCase


class EnvExampleTests(SimpleTestCase):
    # --- env("X") ohne Default fehlt der Wert, startet die Anwendung nicht.
    REQUIRED_RE = re.compile(r'env\("([A-Z_]+)"\)')
    # --- Jede Form von env(...)-Zugriff, auch mit Default.
    ANY_RE = re.compile(r'env(?:\.\w+)?\(\s*"([A-Z_]+)"')
    DOCUMENTED_RE = re.compile(r"^([A-Z_]+)=", re.MULTILINE)
    # --- Next.js liest Laufzeit-/Build-Env über process.env.NAME.
    FRONTEND_ENV_RE = re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        backend_dir = Path(__file__).resolve().parent.parent
        repo_root = backend_dir.parent
        cls.settings_source = (backend_dir / "config" / "settings.py").read_text()
        cls.example = (repo_root / ".env.example").read_text()
        frontend_src = repo_root / "frontend" / "src"
        cls.frontend_source = "\n".join(
            path.read_text()
            for path in frontend_src.rglob("*")
            if path.suffix in {".ts", ".tsx", ".js", ".mjs"}
        )

    def documented(self) -> set[str]:
        return set(self.DOCUMENTED_RE.findall(self.example))

    def read_by_apps(self) -> set[str]:
        return set(self.ANY_RE.findall(self.settings_source)) | set(
            self.FRONTEND_ENV_RE.findall(self.frontend_source)
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
            "Django noch vom Frontend gelesen.",
        )
