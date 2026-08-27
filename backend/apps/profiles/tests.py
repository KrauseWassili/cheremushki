from django.test import SimpleTestCase

from .telegram import (
    InvalidTelegramUsername,
    build_telegram_dm_url,
    normalize_telegram_username,
    parse_telegram_username,
)

ACCEPTED = [
    ("durov", "durov"),
    ("@durov", "durov"),
    ("  @Durov  ", "durov"),
    ("t.me/durov", "durov"),
    ("https://t.me/durov", "durov"),
    ("http://www.t.me/durov/", "durov"),
    ("HTTPS://T.ME/Durov", "durov"),
    ("https://t.me/durov?start=ref", "durov"),
    ("https://t.me/durov#anchor", "durov"),
    ("https://telegram.me/durov", "durov"),
    ("@https://t.me/durov", "durov"),
    ("https://t.me/@durov", "durov"),
]

REJECTED = [
    None,
    "",
    "   ",
    "ab",
    "a" * 33,
    "hat leerzeichen",
    "böse",
    "du\nrov",
    "https://evil.example.com/durov",
    "javascript://t.me/durov",
    "https://t.me/joinchat/AbCdEf",
    "https://t.me/+79001234567",
    "https://t.me/durov/1234",
    "https://t.me/",
    "joinchat",
    "../../etc/passwd",
    "durov/../admin",
]

# --- Von Telegram heute wird nicht mehr vergeben. --- #
LEGACY_SHAPES = ["12345", "_durov", "durov_", "du__rov"]


class ParseTelegramUsernameTests(SimpleTestCase):
    def test_akzeptiert_gaengige_schreibweisen(self):
        for raw, expected in ACCEPTED:
            with self.subTest(raw=raw):
                self.assertEqual(parse_telegram_username(raw, strict=False), expected)

    def test_lehnt_unbrauchbares_ab(self):
        for raw in REJECTED:
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidTelegramUsername):
                    parse_telegram_username(raw, strict=False)

    def test_strict_erzwingt_telegram_namensregeln(self):
        for raw in LEGACY_SHAPES:
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidTelegramUsername):
                    parse_telegram_username(raw, strict=True)

    def test_legacy_handles_bleiben_ohne_strict_nutzbar(self):
        for raw in LEGACY_SHAPES:
            with self.subTest(raw=raw):
                self.assertTrue(parse_telegram_username(raw, strict=False))

    def test_vier_zeichen_handles_sind_erlaubt(self):
        self.assertEqual(parse_telegram_username("evgn"), "evgn")

    def test_umschliessender_whitespace_wird_getrimmt_nicht_geschmuggelt(self):
        """
        Trailing \\n ist Whitespace und wird getrimmt – nicht durchgelassen.

        Wichtig ist der Unterschied zur '$'-Falle: Ein Newline innerhalb des
        Handles darf nie durchkommen (siehe REJECTED), am Rand wird er entfernt.
        """
        self.assertEqual(parse_telegram_username("durov\n"), "durov")


class NormalizeTelegramUsernameTests(SimpleTestCase):
    def test_gibt_none_statt_exception(self):
        self.assertIsNone(normalize_telegram_username("https://evil.example.com/x"))
        self.assertIsNone(normalize_telegram_username(None))

    def test_kanonisiert_wie_parse(self):
        self.assertEqual(normalize_telegram_username(" @Durov "), "durov")


class BuildTelegramDmUrlTests(SimpleTestCase):
    def test_baut_link(self):
        self.assertEqual(build_telegram_dm_url("Durov"), "https://t.me/durov")

    def test_validiert_erneut(self):
        with self.assertRaises(InvalidTelegramUsername):
            build_telegram_dm_url("evil.example.com/x")
