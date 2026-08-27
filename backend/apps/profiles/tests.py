import io
from unittest import mock

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.bot.models import TelegramInvite

from .models import DIRECTORY_REQUIRED_FIELDS, ContactMode, MemberProfile
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
    def test_accepts_common_spellings(self):
        for raw, expected in ACCEPTED:
            with self.subTest(raw=raw):
                self.assertEqual(parse_telegram_username(raw, strict=False), expected)

    def test_rejects_useless_items(self):
        for raw in REJECTED:
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidTelegramUsername):
                    parse_telegram_username(raw, strict=False)

    def test_strict_enforces_telegram_naming_rules(self):
        for raw in LEGACY_SHAPES:
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidTelegramUsername):
                    parse_telegram_username(raw, strict=True)

    def test_legacy_handles_remain_usable_without_strict(self):
        for raw in LEGACY_SHAPES:
            with self.subTest(raw=raw):
                self.assertTrue(parse_telegram_username(raw, strict=False))

    def test_four_characters_are_allowed(self):
        self.assertEqual(parse_telegram_username("evgn"), "evgn")

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(parse_telegram_username("durov\n"), "durov")


class NormalizeTelegramUsernameTests(SimpleTestCase):
    def test_returns_none_instead_of_an_exception(self):
        self.assertIsNone(normalize_telegram_username("https://evil.example.com/x"))
        self.assertIsNone(normalize_telegram_username(None))

    def test_canonized_like_parse(self):
        self.assertEqual(normalize_telegram_username(" @Durov "), "durov")


class BuildTelegramDmUrlTests(SimpleTestCase):
    def test_build_link(self):
        self.assertEqual(build_telegram_dm_url("Durov"), "https://t.me/durov")

    def test_validated_again(self):
        with self.assertRaises(InvalidTelegramUsername):
            build_telegram_dm_url("evil.example.com/x")


COMPLETE_PROFILE = {
    "city": "Berlin",
    "headline": "Designerin",
    "bio": "Kurz über mich",
    "can_help_with": "Design-Reviews",
    "looking_for": "Sparring zu UX",
}


def make_profile(
    *, active: bool = True, avatar: str | None = "avatars/user-1.jpg", **fields
):
    """
    Profil im Speicher, ohne DB die Regel ist reine Feldlogik.
    """
    user = CustomUser(
        id=1, email="a@example.com", first_name="Anna", last_name="B", is_active=active
    )
    profile = MemberProfile(user=user, slug="anna-b", **{**COMPLETE_PROFILE, **fields})
    if avatar:
        profile.avatar = avatar
    return profile


class MissingDirectoryFieldsTests(SimpleTestCase):
    def test_complete_profile_has_no_gaps(self):
        self.assertEqual(make_profile().missing_directory_fields(), [])

    def test_each_required_field_is_detected_individually(self):
        for field in DIRECTORY_REQUIRED_FIELDS:
            with self.subTest(field=field):
                kwargs = {"avatar": None} if field == "avatar" else {field: ""}
                self.assertEqual(
                    make_profile(**kwargs).missing_directory_fields(), [field]
                )

    def test_order_follows_the_form(self):
        profile = make_profile(avatar=None, city="", bio="")
        self.assertEqual(profile.missing_directory_fields(), ["avatar", "city", "bio"])

    def test_space_does_not_count_as_content(self):
        self.assertEqual(make_profile(bio="   ").missing_directory_fields(), ["bio"])


class ComputeDirectoryReadyTests(SimpleTestCase):
    def test_complete_and_active_is_ready(self):
        self.assertTrue(make_profile().compute_directory_ready())

    def test_inactive_account_is_never_ready(self):
        """Auch bei vollständigem Profil: Wer nicht aktiviert ist, gehört nicht
        ins Verzeichnis – und bekommt keine Einladung."""
        self.assertFalse(make_profile(active=False).compute_directory_ready())

    def test_gap_prevents_readiness(self):
        self.assertFalse(make_profile(looking_for="").compute_directory_ready())


class RefreshDirectoryVisibilityTests(SimpleTestCase):
    def test_edge_incomplete_to_complete_is_reported(self):
        profile = make_profile()
        profile.is_directory_visible = False
        self.assertTrue(profile.refresh_directory_visibility(save=False))
        self.assertTrue(profile.is_directory_visible)

    def test_profile_already_visible_does_not_report_a_cross(self):
        """Sonst löst jedes weitere Speichern eine zweite Einladung aus."""
        profile = make_profile()
        profile.is_directory_visible = True
        self.assertFalse(profile.refresh_directory_visibility(save=False))

    def test_step_back_to_incomplete_reports_no_edge(self):
        profile = make_profile(bio="")
        profile.is_directory_visible = True
        self.assertFalse(profile.refresh_directory_visibility(save=False))
        self.assertFalse(profile.is_directory_visible)

    def test_incomplete_remains_incomplete(self):
        profile = make_profile(city="")
        profile.is_directory_visible = False
        self.assertFalse(profile.refresh_directory_visibility(save=False))


class MyProfileEndpointTests(TestCase):
    def setUp(self):
        mock.patch(
            "apps.bot.tasks.profile_post.sync_telegram_profile_post.delay"
        ).start()
        self.addCleanup(mock.patch.stopall)

        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_empty_profile_reports_all_gaps(self):
        response = self.client.get("/api/v1/profiles/user/me/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["directory_ready"])
        self.assertEqual(
            response.data["missing_fields"], list(DIRECTORY_REQUIRED_FIELDS)
        )

    def test_partially_filled_profile_reports_only_remaining_gaps(self):
        self.client.patch(
            "/api/v1/profiles/user/me/",
            {"city": "Berlin", "headline": "Designerin"},
            format="json",
        )
        response = self.client.get("/api/v1/profiles/user/me/")
        self.assertEqual(
            response.data["missing_fields"],
            ["avatar", "bio", "can_help_with", "looking_for"],
        )

    def test_invite_status_comes_with_every_response(self):
        response = self.client.get("/api/v1/profiles/user/me/")
        self.assertIn("invite_sent", response.data)
        self.assertFalse(response.data["invite_sent"])

        TelegramInvite.objects.create(user=self.user, invite_sent_at=timezone.now())

        response = self.client.patch(
            "/api/v1/profiles/user/me/", {"city": "Berlin"}, format="json"
        )
        self.assertTrue(
            response.data["invite_sent"],
            "Die PATCH-Antwort muss den aktuellen Einladungsstand tragen.",
        )

    def test_public_directory_reveals_no_vulnerabilities(self):
        """
        directory_ready/missing_fields gehören nur ins eigene Profil.
        """
        profile = MemberProfile(
            user=self.user, is_directory_visible=True, **COMPLETE_PROFILE
        )
        profile.ensure_unique_slug()
        profile.save()

        response = self.client.get(f"/api/v1/profiles/{profile.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("missing_fields", response.data)
        self.assertNotIn("directory_ready", response.data)


ANONYMIZED_VALUES: dict[str, object] = {
    "headline": "",
    "city": "",
    "profession": "",
    "company": "",
    "position": "",
    "bio": "",
    "can_help_with": "",
    "looking_for": "",
    "telegram_username": "",
    "linkedin_url": "",
    "website_url": "",
    "telegram_group_url": "",
    "tags": [],
    "languages": [],
    "achievements": [],
    "contact_mode": ContactMode.CLOSED,
    "is_directory_visible": False,
    "avatar_position_x": MemberProfile._meta.get_field("avatar_position_x").default,
    "avatar_position_y": MemberProfile._meta.get_field("avatar_position_y").default,
    "avatar_scale": MemberProfile._meta.get_field("avatar_scale").default,
    "avatar_crop_size": MemberProfile._meta.get_field("avatar_crop_size").default,
}

#: Dateifelder – geprüft wird, dass keine Datei mehr zugeordnet ist.
ANONYMIZED_FILE_FIELDS = ("avatar", "avatar_original")

#: Abgeleitet statt geleert.
ANONYMIZED_DERIVED_FIELDS = ("slug",)

#: Bewusst erhalten, mit Begründung.
PRESERVED_FIELDS: dict[str, str] = {
    "id": "Primärschlüssel – die Zeile bleibt bestehen.",
    "user": (
        "Fremdschlüssel. Ohne die Zeile brächen ContactRequest und "
        "TelegramInvite; gelöscht wird der Inhalt, nicht die Struktur."
    ),
}


def one_pixel_png() -> SimpleUploadedFile:
    """Kleinstes gültiges PNG – ImageField verlangt ein lesbares Bild."""
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(buffer, format="PNG")
    return SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png")


class AnonymizeFieldCoverageTests(SimpleTestCase):
    def classified(self) -> set[str]:
        return (
            set(ANONYMIZED_VALUES)
            | set(ANONYMIZED_FILE_FIELDS)
            | set(ANONYMIZED_DERIVED_FIELDS)
            | set(PRESERVED_FIELDS)
        )

    def concrete_fields(self) -> set[str]:
        return {f.name for f in MemberProfile._meta.get_fields() if f.concrete}

    def test_every_field_is_classified(self):
        """Neue Felder müssen eine Entscheidung bekommen: leeren oder behalten."""
        unclassified = self.concrete_fields() - self.classified()
        self.assertEqual(
            unclassified,
            set(),
            "Neue Felder auf MemberProfile: Entweder in anonymize() leeren und "
            "in ANONYMIZED_VALUES aufnehmen, oder mit Begründung in "
            "PRESERVED_FIELDS eintragen.",
        )

    def test_no_classification_without_field(self):
        self.assertEqual(self.classified() - self.concrete_fields(), set())

    def test_no_field_is_doubly_classified(self):
        cleared = (
            set(ANONYMIZED_VALUES)
            | set(ANONYMIZED_FILE_FIELDS)
            | set(ANONYMIZED_DERIVED_FIELDS)
        )
        self.assertEqual(cleared & set(PRESERVED_FIELDS), set())


class AnonymizeTests(TestCase):
    """
    Prüft, ob anonymize() das tut, was die Klassifikation behauptet.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        # Jedes zu leerende Feld vorher belegen – ein Test gegen ein leeres
        # Profil würde auch bei einer wirkungslosen anonymize() grün.
        self.profile = MemberProfile(
            user=self.user,
            headline="Designerin",
            city="Berlin",
            profession="Design",
            company="Acme",
            position="Lead",
            bio="Kurz über mich",
            can_help_with="Design-Reviews",
            looking_for="Sparring",
            tags=["design", "ux"],
            languages=["ru", "de"],
            achievements=["Preis"],
            telegram_username="anna",
            linkedin_url="https://linkedin.com/in/anna",
            website_url="https://anna.example",
            telegram_group_url="https://t.me/annagroup",
            contact_mode=ContactMode.DIRECT,
            is_directory_visible=True,
            avatar_position_x=0.1,
            avatar_position_y=0.2,
            avatar_scale=2.5,
            avatar_crop_size=0.4,
        )
        self.profile.avatar.save("user-x.png", one_pixel_png(), save=False)
        self.profile.avatar_original.save(
            "user-x-orig.png", one_pixel_png(), save=False
        )
        self.profile.ensure_unique_slug()
        self.profile.save()

    def test_precondition_all_fields_are_populated(self):
        for name, empty in ANONYMIZED_VALUES.items():
            with self.subTest(field=name):
                self.assertNotEqual(getattr(self.profile, name), empty)
        for name in ANONYMIZED_FILE_FIELDS:
            with self.subTest(field=name):
                self.assertTrue(getattr(self.profile, name))

    def test_all_classified_fields_are_cleared(self):
        self.profile.anonymize()
        self.profile.refresh_from_db()

        for name, expected in ANONYMIZED_VALUES.items():
            with self.subTest(field=name):
                self.assertEqual(getattr(self.profile, name), expected)

    def test_files_are_dereferenced_and_removed_from_storage(self):
        paths = [getattr(self.profile, n).name for n in ANONYMIZED_FILE_FIELDS]
        for path in paths:
            self.assertTrue(default_storage.exists(path))

        self.profile.anonymize()
        self.profile.refresh_from_db()

        for name in ANONYMIZED_FILE_FIELDS:
            with self.subTest(field=name):
                self.assertFalse(getattr(self.profile, name))
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(default_storage.exists(path))

    def test_slug_is_derived(self):
        self.profile.anonymize()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.slug, f"deleted-{self.user.pk}")

    def test_preserved_fields_remain(self):
        pk, user_id = self.profile.pk, self.profile.user_id
        self.profile.anonymize()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pk, pk)
        self.assertEqual(self.profile.user_id, user_id)

    def test_anonymized_profile_is_not_directory_ready(self):
        self.profile.anonymize()
        self.assertFalse(self.profile.compute_directory_ready())
