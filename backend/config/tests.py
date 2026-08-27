import re
from pathlib import Path

from django.test import SimpleTestCase


class EnvExampleTests(SimpleTestCase):
    # --- env("X") ohne Default fehlt der Wert, startet die Anwendung nicht.
    REQUIRED_RE = re.compile(r'env\("([A-Z_]+)"\)')
    # --- Jede Form von env(...)-Zugriff, auch mit Default.
    ANY_RE = re.compile(r'env(?:\.\w+)?\(\s*"([A-Z_]+)"')
    DOCUMENTED_RE = re.compile(r"^([A-Z_]+)=", re.MULTILINE)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        backend_dir = Path(__file__).resolve().parent.parent
        cls.settings_source = (backend_dir / "config" / "settings.py").read_text()
        cls.example = (backend_dir.parent / ".env.example").read_text()

    def documented(self) -> set[str]:
        return set(self.DOCUMENTED_RE.findall(self.example))

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
        self.assertEqual(
            self.documented() - set(self.ANY_RE.findall(self.settings_source)),
            set(),
            "Diese Variablen stehen in .env.example, werden aber nirgends gelesen.",
        )
