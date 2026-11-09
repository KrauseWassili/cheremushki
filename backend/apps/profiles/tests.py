import io
import os
import shutil
import struct
import tempfile
from unittest import mock

from asgiref.sync import async_to_sync, sync_to_async
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.apps import apps as global_apps
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import CustomUser
from apps.accounts.services.email import ResendError
from apps.bot.models import TelegramInvite

from .avatar_files import (
    AVATAR_DIR,
    AVATAR_ORIGINALS_DIR,
    MAX_AVATAR_EDGE,
    MAX_AVATAR_PIXELS,
    MAX_AVATAR_UPLOAD_BYTES,
    UNSUPPORTED_FORMAT_MESSAGE,
    InvalidAvatarImage,
    strip_image_metadata,
)
from . import views as profile_views
from .hashtags import (
    MAX_HASHTAG_LENGTH,
    InvalidHashtag,
    normalize_hashtag,
    parse_hashtag,
)
from .models import (
    DIRECTORY_REQUIRED_FIELDS,
    RESERVED_SLUGS,
    ContactMode,
    ContactRequest,
    ContactRequestStatus,
    MemberProfile,
    ProfileTag,
)
from .serializers import MAX_PROFILE_TAGS
from .tasks import send_contact_request_email
from .services import MAX_SUGGESTION_LIMIT
from .tag_vocabulary import (
    ALL_PROFILE_TAGS,
    COMMUNITY_PROFILE_TAGS,
    INITIAL_PROFILE_TAGS,
    find_name_collisions,
    seed_profile_tags,
)
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

# Wie in accounts/tests.py: cache.clear() darf nie den echten Redis leeren.
LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "profiles-tests",
    }
}


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
    "languages": [],
    "achievements": [],
    "contact_mode": ContactMode.CLOSED,
    "is_directory_visible": False,
    "avatar_position_x": MemberProfile._meta.get_field("avatar_position_x").default,
    "avatar_position_y": MemberProfile._meta.get_field("avatar_position_y").default,
    "avatar_scale": MemberProfile._meta.get_field("avatar_scale").default,
    "avatar_crop_size": MemberProfile._meta.get_field("avatar_crop_size").default,
}

# --- Dateifelder: geprüft wird, dass keine Datei mehr zugeordnet ist.
ANONYMIZED_FILE_FIELDS = ("avatar", "avatar_original")

# Relationsfelder: geprüft wird, dass keine Zuordnung mehr besteht. Der
# TaggableManager lässt sich nicht mit einem Leerwert vergleichen, deshalb eine
# eigene Kategorie statt eines Eintrags in ANONYMIZED_VALUES.
ANONYMIZED_RELATION_FIELDS = ("tags",)

# --- Abgeleitet statt geleert.
ANONYMIZED_DERIVED_FIELDS = ("slug",)

PRESERVED_FIELDS: dict[str, str] = {
    "id": "Primärschlüssel – die Zeile bleibt bestehen.",
    "user": (
        "Fremdschlüssel. Ohne die Zeile brächen ContactRequest und "
        "TelegramInvite; gelöscht wird der Inhalt, nicht die Struktur."
    ),
}


def one_pixel_png() -> SimpleUploadedFile:
    """
    Kleinstes gültiges PNG ImageField verlangt ein lesbares Bild.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(buffer, format="PNG")
    return SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png")


class AnonymizeFieldCoverageTests(SimpleTestCase):
    def classified(self) -> set[str]:
        return (
            set(ANONYMIZED_VALUES)
            | set(ANONYMIZED_FILE_FIELDS)
            | set(ANONYMIZED_RELATION_FIELDS)
            | set(ANONYMIZED_DERIVED_FIELDS)
            | set(PRESERVED_FIELDS)
        )

    def concrete_fields(self) -> set[str]:
        return {f.name for f in MemberProfile._meta.get_fields() if f.concrete}

    def test_every_field_is_classified(self):
        """
        Neue Felder müssen eine Entscheidung bekommen: leeren oder behalten.
        """
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
            | set(ANONYMIZED_RELATION_FIELDS)
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
        # --- Tags gehen erst nach dem save() der Admin braucht eine PK.
        self.tags = [make_tag("дизайн", "Дизайн"), make_tag("ux", "UX")]
        self.profile.tags.set(self.tags)

    def test_precondition_all_fields_are_populated(self):
        for name, empty in ANONYMIZED_VALUES.items():
            with self.subTest(field=name):
                self.assertNotEqual(getattr(self.profile, name), empty)
        for name in ANONYMIZED_FILE_FIELDS:
            with self.subTest(field=name):
                self.assertTrue(getattr(self.profile, name))
        for name in ANONYMIZED_RELATION_FIELDS:
            with self.subTest(field=name):
                self.assertTrue(getattr(self.profile, name).exists())

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

        # Gelöscht wird erst nach dem Commit, siehe schedule_avatar_file_deletion.
        with self.captureOnCommitCallbacks(execute=True):
            self.profile.anonymize()
        self.profile.refresh_from_db()

        for name in ANONYMIZED_FILE_FIELDS:
            with self.subTest(field=name):
                self.assertFalse(getattr(self.profile, name))
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(default_storage.exists(path))

    def test_tag_assignments_are_cleared_but_vocabulary_survives(self):
        self.profile.anonymize()
        self.profile.refresh_from_db()

        self.assertEqual(list(self.profile.tags.names()), [])
        # --- Das Vokabular gehört dem Club, nicht dem Mitglied.
        self.assertEqual(
            ProfileTag.objects.filter(pk__in=[t.pk for t in self.tags]).count(),
            len(self.tags),
        )

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


ACCEPTED_HASHTAGS = [
    ("#IT", "it"),
    ("IT", "it"),
    ("  it  ", "it"),
    ("Веб Разработка", "веб_разработка"),
    ("веб-разработка", "веб_разработка"),
    ("крипта!!!", "крипта"),
    ("--tag--", "tag"),
    ("#Крипта", "крипта"),
    ("Бремен", "бремен"),
    ("ＩＴ", "it"),
]

REJECTED_HASHTAGS = [
    None,
    "",
    "   ",
    "#",
    "＃",
    "123",
    "2024",
    "🎉",
    "!!!",
    "x" * 65,
]


class ParseHashtagTests(SimpleTestCase):
    def test_accepted_values_are_canonized(self):
        for raw, expected in ACCEPTED_HASHTAGS:
            with self.subTest(raw=raw):
                self.assertEqual(parse_hashtag(raw), expected)

    def test_rejected_values_raise(self):
        for raw in REJECTED_HASHTAGS:
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidHashtag):
                    parse_hashtag(raw)

    def test_maximum_length_is_still_accepted(self):
        self.assertEqual(parse_hashtag("x" * 64), "x" * 64)


class NormalizeHashtagTests(SimpleTestCase):
    def test_rejected_values_become_none(self):
        for raw in REJECTED_HASHTAGS:
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_hashtag(raw))

    def test_canonized_like_parse(self):
        self.assertEqual(normalize_hashtag(" #Крипта "), "крипта")


def make_tag(name: str, label: str = "", *, is_active: bool = True) -> ProfileTag:
    tag, _ = ProfileTag.objects.update_or_create(
        name=parse_hashtag(name),
        defaults={"label": label, "is_active": is_active},
    )
    return tag


class ProfileTagModelTests(TestCase):
    def test_name_is_canonized_on_save(self):
        tag = ProfileTag.objects.create(name="#Мой Тег", label="Мой тег")
        tag.refresh_from_db()
        self.assertEqual(tag.name, "мой_тег")

    def test_cyrillic_names_get_distinct_slugs(self):

        first = ProfileTag.objects.create(name="крипта тест")
        second = ProfileTag.objects.create(name="дизайн тест")
        self.assertTrue(first.slug)
        self.assertTrue(second.slug)
        self.assertNotEqual(first.slug, second.slug)

    def test_display_label_falls_back_to_name(self):
        tag = make_tag("отдельный_тег")
        self.assertEqual(tag.display_label, "отдельный_тег")
        tag.label = "Отдельный тег"
        self.assertEqual(tag.display_label, "Отдельный тег")

    def test_hashtag_property_prefixes_the_name(self):
        self.assertEqual(make_tag("отдельный_тег").hashtag, "#отдельный_тег")


def seed_tags() -> dict[str, ProfileTag]:
    return {
        "it": make_tag("it", "IT"),
        "дизайн": make_tag("дизайн", "Дизайн"),
        "крипта": make_tag("крипта", "Крипта"),
        "веб_разработка": make_tag("веб_разработка", "Веб-разработка"),
        "архив": make_tag("архив", "Архив", is_active=False),
    }


class ProfileTagWriteTests(TestCase):

    def setUp(self):
        mock.patch(
            "apps.bot.tasks.profile_post.sync_telegram_profile_post.delay"
        ).start()
        self.addCleanup(mock.patch.stopall)

        self.tags = seed_tags()
        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def patch_tags(self, tags):
        return self.client.patch(
            "/api/v1/profiles/user/me/", {"tags": tags}, format="json"
        )

    def test_known_tags_are_accepted_in_any_spelling(self):
        response = self.patch_tags(["#IT", "  Крипта ", "Веб-разработка"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tags"], ["it", "веб_разработка", "крипта"])

    def test_duplicates_collapse_into_one_assignment(self):
        response = self.patch_tags(["it", "#IT", "  it  "])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tags"], ["it"])

    def test_unknown_tag_is_rejected_and_named(self):
        response = self.patch_tags(["it", "нетакого"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("нетакого", str(response.data["tags"]))

    def test_unknown_tag_is_not_silently_created(self):
        before = ProfileTag.objects.count()
        self.patch_tags(["нетакого"])
        self.assertEqual(ProfileTag.objects.count(), before)
        self.assertFalse(ProfileTag.objects.filter(name="нетакого").exists())

    def test_inactive_tag_is_rejected(self):
        response = self.patch_tags(["архив"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("архив", str(response.data["tags"]))

    def test_uncanonizable_value_is_rejected_and_named(self):
        response = self.patch_tags(["123"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("123", str(response.data["tags"]))

    def test_too_many_tags_are_rejected(self):
        response = self.patch_tags([f"tag{index}" for index in range(11)])
        self.assertEqual(response.status_code, 400)
        self.assertIn(str(MAX_PROFILE_TAGS), str(response.data["tags"]))

    def test_empty_list_clears_the_assignments(self):
        self.patch_tags(["it", "дизайн"])
        response = self.patch_tags([])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tags"], [])

    def test_patch_without_tags_keeps_them(self):
        self.patch_tags(["it"])
        response = self.client.patch(
            "/api/v1/profiles/user/me/", {"city": "Бремен"}, format="json"
        )
        self.assertEqual(response.data["tags"], ["it"])

    def test_tags_detail_carries_labels_and_hashtags(self):
        response = self.patch_tags(["it"])
        self.assertEqual(
            response.data["tags_detail"],
            [{"name": "it", "label": "IT", "hashtag": "#it"}],
        )


def make_visible_profile(email: str, *, city: str = "Бремен", **fields):
    user = CustomUser.objects.create_user(
        email=email,
        password="Str0ng!Passwort",
        first_name="Anna",
        last_name="B",
        is_active=True,
    )
    profile = MemberProfile(
        user=user,
        is_directory_visible=True,
        **{**COMPLETE_PROFILE, "city": city, **fields},
    )
    profile.ensure_unique_slug()
    profile.save()
    return profile


class DirectoryTagFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tags = seed_tags()
        cls.both = make_visible_profile("both@example.com")
        cls.both.tags.set([cls.tags["it"], cls.tags["крипта"]])
        cls.only_it = make_visible_profile("it@example.com")
        cls.only_it.tags.set([cls.tags["it"]])
        cls.untagged = make_visible_profile("none@example.com")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.both.user)

    def slugs(self, query: str) -> list[str]:
        response = self.client.get(f"/api/v1/profiles/{query}")
        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        return sorted(item["slug"] for item in results)

    def test_single_tag_filters_the_directory(self):
        self.assertEqual(
            self.slugs("?tags=it"), sorted([self.both.slug, self.only_it.slug])
        )

    def test_multiple_tags_are_and_combined(self):
        self.assertEqual(self.slugs("?tags=it,крипта"), [self.both.slug])

    def test_filter_value_is_canonized(self):
        self.assertEqual(self.slugs("?tags=%23IT"), self.slugs("?tags=it"))

    def test_unknown_tag_yields_an_empty_list_not_an_error(self):
        self.assertEqual(self.slugs("?tags=нетакого"), [])

    def test_uncanonizable_tag_yields_an_empty_list_not_an_error(self):
        self.assertEqual(self.slugs("?tags=123"), [])

    def test_profile_appears_once_per_matching_tag_set(self):
        response = self.client.get("/api/v1/profiles/?tags=it,крипта")
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)


class TagSuggestionEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tags = seed_tags()
        popular = make_visible_profile("popular@example.com")
        popular.tags.set([cls.tags["крипта"], cls.tags["it"]])
        second = make_visible_profile("second@example.com")
        second.tags.set([cls.tags["крипта"]])
        # Unsichtbares Profil: Seine Zuordnung darf nicht mitzählen.
        hidden = make_visible_profile("hidden@example.com")
        hidden.is_directory_visible = False
        hidden.save()
        hidden.tags.set([cls.tags["it"]])
        cls.user = popular.user

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def get(self, query: str = ""):
        response = self.client.get(f"/api/v1/profiles/tags/{query}")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_requires_authentication(self):
        anonymous = APIClient()
        self.assertIn(anonymous.get("/api/v1/profiles/tags/").status_code, (401, 403))

    def test_only_active_tags_are_suggested(self):
        names = [item["name"] for item in self.get()]
        self.assertNotIn("архив", names)
        self.assertIn("it", names)

    def test_sorted_by_usage_among_visible_profiles(self):
        items = {item["name"]: item["usage_count"] for item in self.get()}
        self.assertEqual(items["крипта"], 2)
        self.assertEqual(items["it"], 1, "Unsichtbare Profile zählen nicht mit.")
        self.assertEqual([item["name"] for item in self.get()][0], "крипта")

    def test_query_matches_name_and_label(self):
        # "Веб-р" trifft nur das Label (der Name hat "_"), "веб_р" nur den
        # Namen – präzise genug, um "Веб-технологии" auszuschließen.
        self.assertEqual(
            [item["name"] for item in self.get("?q=Веб-р")], ["веб_разработка"]
        )
        self.assertEqual(
            [item["name"] for item in self.get("?q=веб_р")], ["веб_разработка"]
        )

    def test_response_carries_label_and_hashtag(self):
        item = next(item for item in self.get("?q=it") if item["name"] == "it")
        self.assertEqual(item["label"], "IT")
        self.assertEqual(item["hashtag"], "#it")

    def test_limit_is_capped(self):
        self.assertLessEqual(len(self.get("?limit=999")), MAX_SUGGESTION_LIMIT)

    def test_limit_is_respected(self):
        self.assertEqual(len(self.get("?limit=1")), 1)

    def test_broken_limit_falls_back_to_the_default(self):
        self.assertEqual(len(self.get("?limit=abc")), len(self.get()))


class CitySuggestionEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_visible_profile("a@example.com", city="Бремен")
        second = make_visible_profile("b@example.com", city="Бремен")
        make_visible_profile("c@example.com", city="Гамбург")
        hidden = make_visible_profile("d@example.com", city="Берлин")
        hidden.is_directory_visible = False
        hidden.save()
        cls.user = second.user

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def get(self, query: str = ""):
        response = self.client.get(f"/api/v1/profiles/cities/{query}")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_requires_authentication(self):
        anonymous = APIClient()
        self.assertIn(anonymous.get("/api/v1/profiles/cities/").status_code, (401, 403))

    def test_counts_only_visible_profiles(self):
        counts = {item["name"]: item["count"] for item in self.get()}
        self.assertEqual(counts["Бремен"], 2)
        self.assertEqual(counts["Гамбург"], 1)
        self.assertNotIn("Берлин", counts)

    def test_city_carries_its_hashtag_token(self):
        item = next(item for item in self.get() if item["name"] == "Бремен")
        self.assertEqual(item["hashtag"], "бремен")

    def test_query_narrows_the_list(self):
        self.assertEqual([item["name"] for item in self.get("?q=Гам")], ["Гамбург"])

    def test_limit_is_capped(self):
        self.assertLessEqual(len(self.get("?limit=999")), MAX_SUGGESTION_LIMIT)


class ReservedSlugTests(TestCase):
    """
    /profiles/tags/ und /profiles/cities/ sind Routen kein Profil darf sie
    verdecken.
    """

    def setUp(self):
        mock.patch(
            "apps.bot.tasks.profile_post.sync_telegram_profile_post.delay"
        ).start()
        self.addCleanup(mock.patch.stopall)

    def test_reserved_slug_is_rejected_by_the_api(self):
        user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        client = APIClient()
        client.force_authenticate(user)
        for slug in sorted(RESERVED_SLUGS):
            with self.subTest(slug=slug):
                response = client.patch(
                    "/api/v1/profiles/user/me/", {"slug": slug}, format="json"
                )
                self.assertEqual(response.status_code, 400)

    def test_generated_slug_dodges_reserved_values(self):
        user = CustomUser.objects.create_user(
            email="tags@example.com",
            password="Str0ng!Passwort",
            first_name="Tags",
            last_name="",
            is_active=True,
        )
        profile = MemberProfile(user=user)
        profile.ensure_unique_slug()
        self.assertNotIn(profile.slug, RESERVED_SLUGS)
        self.assertEqual(profile.slug, "tags-2")


class ProfileCaptionTagTests(TestCase):
    """
    Die Telegram-Ausgabe: Nur mit '#' davor ist ein Tag dort auffindbar.
    """

    @classmethod
    def setUpTestData(cls):
        cls.tags = seed_tags()
        cls.profile = make_visible_profile("anna@example.com", city="Бремен")

    def caption(self, profile=None) -> str:
        from apps.bot.services.profile_card import build_profile_caption

        return build_profile_caption(profile or self.profile)

    def test_tags_are_rendered_as_hashtags(self):
        self.profile.tags.set([self.tags["it"], self.tags["крипта"]])
        caption = self.caption()
        self.assertIn("#it", caption)
        self.assertIn("#крипта", caption)

    def test_tags_are_space_separated(self):
        self.profile.tags.set([self.tags["it"], self.tags["крипта"]])
        self.assertIn("#it #крипта", self.caption())

    def test_without_tags_the_section_stays_empty(self):
        self.profile.tags.clear()
        self.assertIn("<b>Теги</b>\n—", self.caption())

    def test_city_is_rendered_as_a_hashtag(self):
        self.assertIn("· #бремен", self.caption())

    def test_uncanonizable_city_stays_plain_text(self):
        profile = make_visible_profile("plain@example.com", city="123")
        self.assertIn("· 123", self.caption(profile))
        self.assertNotIn("#123", self.caption(profile))

    def test_missing_city_falls_back_to_the_placeholder(self):
        profile = make_visible_profile("nocity@example.com", city="")
        self.assertIn("· —", self.caption(profile))


class SeedProfileTagsCommandTests(TestCase):
    def test_seeding_is_idempotent(self):
        call_command("seed_profile_tags")
        after_first = ProfileTag.objects.count()
        self.assertEqual(
            after_first, len({parse_hashtag(name) for name, _ in ALL_PROFILE_TAGS})
        )

        call_command("seed_profile_tags")
        self.assertEqual(ProfileTag.objects.count(), after_first)

    def test_seeded_names_are_canonical(self):
        call_command("seed_profile_tags")
        for name in ProfileTag.objects.values_list("name", flat=True):
            with self.subTest(name=name):
                self.assertEqual(parse_hashtag(name), name)

    def test_existing_tag_is_not_overwritten(self):
        make_tag("it", "Eigenes Label", is_active=False)
        call_command("seed_profile_tags")
        tag = ProfileTag.objects.get(name="it")
        self.assertEqual(tag.label, "Eigenes Label")
        self.assertFalse(tag.is_active)


class ContactRequestMailTests(TestCase):
    """
    Der Versand läuft über die Resend-API. Der Status der Anfrage muss den
    Ausgang des Versands beschreiben – er ist das Einzige, woran im Admin
    später erkennbar ist, ob die Mail draußen war.
    """

    def setUp(self):
        self.sender = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        self.receiver = CustomUser.objects.create_user(
            email="boris@example.com",
            password="Str0ng!Passwort",
            first_name="Boris",
            last_name="C",
            is_active=True,
        )
        profile = MemberProfile(user=self.receiver, contact_mode=ContactMode.REQUEST)
        profile.ensure_unique_slug()
        profile.save()
        self.contact = ContactRequest.objects.create(
            from_user=self.sender, to_profile=profile, message="Hallo!"
        )

    def test_successful_delivery_marks_the_request_as_sent(self):
        with mock.patch("apps.profiles.tasks.send_email") as send_email:
            send_contact_request_email(self.contact.pk)

        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.kwargs["to"], self.receiver.email)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.status, ContactRequestStatus.SENT)

    def test_mail_text_is_russian_and_informal(self):
        with mock.patch("apps.profiles.tasks.send_email") as send_email:
            send_contact_request_email(self.contact.pk)

        call = send_email.call_args.kwargs
        self.assertIn("Запрос на контакт от", call["subject"])
        self.assertIn(self.sender.full_name, call["subject"])
        self.assertIn("Здравствуй, Boris", call["message"])
        # "с тобой" statt "с вами": die Community duzt.
        self.assertIn("с тобой", call["message"])
        self.assertIn(self.sender.email, call["message"])
        self.assertIn("Hallo!", call["message"])

    def test_permanent_failure_marks_the_request_as_failed(self):
        with mock.patch(
            "apps.profiles.tasks.send_email",
            side_effect=ResendError("Resend down", retryable=False),
        ):
            with self.assertRaises(ResendError):
                send_contact_request_email(self.contact.pk)

        self.contact.refresh_from_db()
        self.assertEqual(self.contact.status, ContactRequestStatus.FAILED)


def canonical_names(vocabulary) -> set[str]:
    return {parse_hashtag(raw_name) for raw_name, _ in vocabulary}


class TagVocabularyTests(SimpleTestCase):
    """
    Die Listen speisen Datenmigrationen. Ein Eintrag, den parse_hashtag
    ablehnt oder umschreibt, würde die Migration abbrechen bzw. einen anderen
    Namen anlegen als im Diff steht.
    """

    VOCABULARIES = {
        "INITIAL_PROFILE_TAGS": INITIAL_PROFILE_TAGS,
        "COMMUNITY_PROFILE_TAGS": COMMUNITY_PROFILE_TAGS,
        "ALL_PROFILE_TAGS": ALL_PROFILE_TAGS,
    }

    def test_vocabulary_entries_resolve_to_valid_hashtags(self):
        for list_name, vocabulary in self.VOCABULARIES.items():
            for raw_name, label in vocabulary:
                with self.subTest(vocabulary=list_name, raw_name=raw_name):
                    name = parse_hashtag(raw_name)
                    self.assertLessEqual(len(name), MAX_HASHTAG_LENGTH)
                    self.assertEqual(parse_hashtag(name), name)
                    self.assertTrue(label)

    def test_vocabulary_initial_list_keeps_its_thirty_entries(self):
        # Migration 0006 ist angewandt – die Liste ist append-only.
        self.assertEqual(len(INITIAL_PROFILE_TAGS), 30)
        self.assertEqual(len(canonical_names(INITIAL_PROFILE_TAGS)), 30)

    def test_vocabulary_all_is_initial_followed_by_community(self):
        self.assertEqual(
            ALL_PROFILE_TAGS, INITIAL_PROFILE_TAGS + COMMUNITY_PROFILE_TAGS
        )

    def test_vocabulary_community_label_example(self):
        self.assertIn(
            ("Бухгалтерский учёт", "Бухгалтерский учёт"), COMMUNITY_PROFILE_TAGS
        )
        self.assertIn("бухгалтерский_учёт", canonical_names(COMMUNITY_PROFILE_TAGS))


class FindNameCollisionsTests(SimpleTestCase):
    def test_find_name_collisions_empty_vocabulary(self):
        self.assertEqual(find_name_collisions([]), {})

    def test_find_name_collisions_unique_names(self):
        self.assertEqual(find_name_collisions([("IT", "IT"), ("дизайн", "Дизайн")]), {})

    def test_find_name_collisions_groups_by_canonical_name(self):
        # "#IT" und "it" landen beide auf "it"; Reihenfolge der Labels bleibt.
        vocabulary = [("IT", "IT"), ("дизайн", "Дизайн"), ("#it", "It-Label")]
        self.assertEqual(find_name_collisions(vocabulary), {"it": ["IT", "It-Label"]})

    def test_find_name_collisions_identical_labels_are_reported(self):
        vocabulary = [("Дизайн", "Дизайн"), ("Дизайн", "Дизайн")]
        self.assertEqual(
            find_name_collisions(vocabulary), {"дизайн": ["Дизайн", "Дизайн"]}
        )

    def test_find_name_collisions_real_vocabulary_has_only_identical_labels(self):
        """
        Unterschiedliche Labels unter einem Namen hießen: eine Schreibweise
        wird nie angelegt. Im ausgelieferten Vokabular soll das nicht vorkommen.
        """
        collisions = find_name_collisions(ALL_PROFILE_TAGS)
        overlap = canonical_names(INITIAL_PROFILE_TAGS) & canonical_names(
            COMMUNITY_PROFILE_TAGS
        )
        self.assertEqual(set(collisions), overlap)
        for name, labels in collisions.items():
            with self.subTest(name=name):
                self.assertEqual(len(set(labels)), 1)


class SeedProfileTagsFunctionTests(TestCase):
    """
    Die Test-DB ist durch die Migrationen bereits geseedet – jeder Test
    startet deshalb mit leerer Tag-Tabelle.
    """

    def setUp(self):
        ProfileTag.objects.all().delete()

    def test_seed_default_creates_only_initial_tags(self):
        created, skipped = seed_profile_tags(ProfileTag)

        self.assertEqual((created, skipped), (30, 0))
        self.assertEqual(
            set(ProfileTag.objects.values_list("name", flat=True)),
            canonical_names(INITIAL_PROFILE_TAGS),
        )
        self.assertFalse(ProfileTag.objects.filter(name="бухгалтерский_учёт").exists())

    def test_seed_duplicate_names_count_once(self):
        # "IT" und "#it" sind derselbe Name: einmal angelegt, nicht als
        # "bereits vorhanden" gezählt. Das erste Label gewinnt.
        created, skipped = seed_profile_tags(
            ProfileTag, [("IT", "IT"), ("#it", "Anderes"), ("дизайн", "Дизайн")]
        )

        self.assertEqual((created, skipped), (2, 0))
        self.assertEqual(ProfileTag.objects.get(name="it").label, "IT")

    def test_seed_existing_tag_counts_as_skipped_and_stays_unchanged(self):
        make_tag("it", "Eigenes Label", is_active=False)

        created, skipped = seed_profile_tags(ProfileTag, [("IT", "IT"), ("HR", "HR")])

        self.assertEqual((created, skipped), (1, 1))
        tag = ProfileTag.objects.get(name="it")
        self.assertEqual(tag.label, "Eigenes Label")
        self.assertFalse(tag.is_active)

    def test_seed_empty_vocabulary_creates_nothing(self):
        self.assertEqual(seed_profile_tags(ProfileTag, []), (0, 0))
        self.assertFalse(ProfileTag.objects.exists())


class SeedProfileTagsCommandFullVocabularyTests(TestCase):
    def setUp(self):
        ProfileTag.objects.all().delete()

    def run_command(self) -> str:
        out = io.StringIO()
        call_command("seed_profile_tags", stdout=out)
        return out.getvalue()

    def test_command_seeds_full_vocabulary_on_empty_table(self):
        output = self.run_command()

        expected = canonical_names(ALL_PROFILE_TAGS)
        self.assertEqual(
            set(ProfileTag.objects.values_list("name", flat=True)), expected
        )
        self.assertIn(f"{len(expected)} angelegt", output)
        self.assertIn(f"({len(expected)} im Vokabular)", output)

    def test_command_second_run_creates_nothing(self):
        self.run_command()
        output = self.run_command()

        unique_count = len(canonical_names(ALL_PROFILE_TAGS))
        self.assertEqual(ProfileTag.objects.count(), unique_count)
        self.assertIn(f"0 angelegt, {unique_count} bereits vorhanden", output)

    def test_command_reports_no_conflicting_collisions(self):
        self.assertNotIn("Namenskollision", self.run_command())


MIGRATION_0008 = "0008_seed_community_profile_tags"
MIGRATION_0007 = "0007_remove_memberprofile_legacy_tags"
# Nur in der Community-Liste, nicht im Startvokabular.
COMMUNITY_ONLY_USED = "йога"
COMMUNITY_ONLY_UNUSED = "кофе"
# In beiden Listen – gehört 0006 und muss den Rollback überleben.
SHARED_WITH_INITIAL = "дизайн"
INITIAL_ONLY = "it"


def tag_profile_with(name: str) -> MemberProfile:
    user = CustomUser.objects.create_user(
        email=f"{name}@example.com",
        password="Str0ng!Passwort",
        first_name="Anna",
        last_name="B",
        is_active=True,
    )
    profile = MemberProfile(user=user)
    profile.ensure_unique_slug()
    profile.save()
    profile.tags.add(ProfileTag.objects.get(name=name))
    return profile


def load_migration_0008():
    import importlib

    return importlib.import_module(f"apps.profiles.migrations.{MIGRATION_0008}")


class CommunityTagMigrationFunctionTests(TestCase):
    """
    Die RunPython-Funktionen direkt mit der aktuellen App-Registry – schnell
    und unabhängig vom Migrationsgraphen. Das Zusammenspiel mit den
    historischen Modellen prüft CommunityTagMigrationExecutorTests.
    """

    def setUp(self):
        self.migration = load_migration_0008()

    def names(self) -> set[str]:
        return set(ProfileTag.objects.values_list("name", flat=True))

    def test_reverse_removes_only_unused_community_tags(self):
        tag_profile_with(COMMUNITY_ONLY_USED)

        self.migration.remove_unused_community_tags(global_apps, None)

        names = self.names()
        self.assertIn(COMMUNITY_ONLY_USED, names)
        self.assertNotIn(COMMUNITY_ONLY_UNUSED, names)
        self.assertIn(SHARED_WITH_INITIAL, names)
        self.assertIn(INITIAL_ONLY, names)
        community_only = canonical_names(COMMUNITY_PROFILE_TAGS) - canonical_names(
            INITIAL_PROFILE_TAGS
        )
        self.assertEqual(names & community_only, {COMMUNITY_ONLY_USED})
        self.assertEqual(names - community_only, canonical_names(INITIAL_PROFILE_TAGS))

    def test_reverse_keeps_profile_assignment(self):
        profile = tag_profile_with(COMMUNITY_ONLY_USED)

        self.migration.remove_unused_community_tags(global_apps, None)

        self.assertEqual(list(profile.tags.names()), [COMMUNITY_ONLY_USED])

    def test_reverse_keeps_unrelated_admin_tags(self):
        make_tag("eigener_tag", "Eigener Tag")

        self.migration.remove_unused_community_tags(global_apps, None)

        self.assertIn("eigener_tag", self.names())

    def test_forward_after_reverse_restores_vocabulary(self):
        self.migration.remove_unused_community_tags(global_apps, None)
        self.migration.seed_community_tags(global_apps, None)

        self.assertTrue(canonical_names(ALL_PROFILE_TAGS) <= self.names())

    def test_forward_is_idempotent(self):
        before = ProfileTag.objects.count()
        self.migration.seed_community_tags(global_apps, None)
        self.assertEqual(ProfileTag.objects.count(), before)


class CommunityTagMigrationExecutorTests(TransactionTestCase):
    """
    Echter Rollback und Re-Apply von 0008 über den MigrationExecutor, also mit
    den historischen Modellen (tagged_profiles muss dort auflösbar sein).

    serialized_rollback: TransactionTestCase leert danach alle Tabellen –
    ohne Wiederherstellung fehlten den folgenden Tests die per Migration
    geseedeten Tags.
    """

    serialized_rollback = True

    def migrate_profiles_to(self, migration_name: str) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("profiles", migration_name)])

    def setUp(self):
        # Auch bei einem Fehlschlag wieder auf den aktuellen Stand, sonst
        # laufen die übrigen Tests gegen ein zurückgerolltes Schema/Vokabular.
        self.addCleanup(self.migrate_to_leaf)

    def migrate_to_leaf(self) -> None:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def names(self) -> set[str]:
        return set(ProfileTag.objects.values_list("name", flat=True))

    def test_migration_0008_reverse_keeps_used_and_initial_tags(self):
        tag_profile_with(COMMUNITY_ONLY_USED)

        self.migrate_profiles_to(MIGRATION_0007)

        names = self.names()
        self.assertIn(COMMUNITY_ONLY_USED, names)
        self.assertNotIn(COMMUNITY_ONLY_UNUSED, names)
        self.assertIn(SHARED_WITH_INITIAL, names)
        self.assertIn(INITIAL_ONLY, names)

    def test_migration_0008_forward_seeds_community_tags(self):
        self.migrate_profiles_to(MIGRATION_0007)
        self.assertNotIn(COMMUNITY_ONLY_UNUSED, self.names())

        self.migrate_profiles_to(MIGRATION_0008)

        self.assertTrue(canonical_names(ALL_PROFILE_TAGS) <= self.names())


# --- Avatar-Dateien: Bereinigung, Upload, Original, Altlasten ------------ #


class TempMediaRootMixin:
    """
    Legt MEDIA_ROOT für jeden Test in ein eigenes Temp-Verzeichnis.

    Avatar-Tests schreiben, löschen und listen Dateien – gegen das echte
    backend/media würden sie sich gegenseitig (und den Dev-Stand) stören.
    """

    def setUp(self):
        super().setUp()
        media_root = tempfile.mkdtemp(prefix="avatar-tests-")
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media_root)
        override.enable()
        self.addCleanup(override.disable)

    def storage_names(self) -> set[str]:
        names: set[str] = set()
        for directory in (AVATAR_DIR, AVATAR_ORIGINALS_DIR):
            try:
                _, files = default_storage.listdir(directory)
            except FileNotFoundError:
                continue
            names.update(f"{directory}/{name}" for name in files)
        return names


def image_bytes(
    size: tuple[int, int] = (4, 4),
    *,
    mode: str = "RGB",
    color=(200, 10, 10),
    image_format: str = "PNG",
    **save_options,
) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format=image_format, **save_options)
    return buffer.getvalue()


def image_upload(name: str = "avatar.png", **kwargs) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, image_bytes(**kwargs), content_type="image/png")


GPS_IFD = 0x8825
ORIENTATION_TAG = 0x0112
XMP_PAYLOAD = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b"<rdf:Description>geheimer-standort</rdf:Description>"
    b"</rdf:RDF></x:xmpmeta>"
)


def jpeg_with_gps_and_xmp() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "Handyhersteller"  # Make
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (53.0, 4.0, 30.0)
    gps[3] = "E"
    gps[4] = (8.0, 48.0, 0.0)
    return image_bytes(image_format="JPEG", exif=exif.tobytes(), xmp=XMP_PAYLOAD)


def opened(content) -> Image.Image:
    content.seek(0)
    return Image.open(io.BytesIO(content.read()))


class StripImageMetadataTests(SimpleTestCase):
    def test_strip_image_metadata_removes_exif_gps_and_xmp(self):
        source = jpeg_with_gps_and_xmp()
        # Vorbedingung: Die Eingabe trägt wirklich GPS und XMP, sonst prüft
        # der Test nichts.
        with Image.open(io.BytesIO(source)) as original:
            self.assertTrue(original.getexif().get_ifd(GPS_IFD))
            self.assertIn("xmp", original.info)

        cleaned = strip_image_metadata(io.BytesIO(source))

        self.assertEqual(cleaned.name, "avatar.jpg")
        with opened(cleaned) as result:
            self.assertEqual(result.format, "JPEG")
            self.assertEqual(dict(result.getexif()), {})
            self.assertNotIn("exif", result.info)
            self.assertNotIn("xmp", result.info)
        cleaned.seek(0)
        raw = cleaned.read()
        self.assertNotIn(b"geheimer-standort", raw)
        self.assertNotIn(b"Handyhersteller", raw)

    def test_strip_image_metadata_applies_exif_orientation(self):
        # 4x2 quer mit Orientation 6 (90° im Uhrzeigersinn drehen) muss als
        # 2x4 hochkant herauskommen – ohne das Tag stünde es sonst falsch.
        exif = Image.Exif()
        exif[ORIENTATION_TAG] = 6
        source = image_bytes((4, 2), image_format="JPEG", exif=exif.tobytes())

        cleaned = strip_image_metadata(io.BytesIO(source))

        with opened(cleaned) as result:
            self.assertEqual(result.size, (2, 4))
            self.assertNotIn(ORIENTATION_TAG, result.getexif())

    def test_strip_image_metadata_downscales_long_edge(self):
        # 3000x1000 → längste Kante 2048, Seitenverhältnis 3:1 → 2048x683.
        source = image_bytes((3000, 1000), image_format="PNG")

        cleaned = strip_image_metadata(io.BytesIO(source))

        with opened(cleaned) as result:
            self.assertEqual(max(result.size), MAX_AVATAR_EDGE)
            self.assertEqual(result.size, (2048, 683))

    def test_strip_image_metadata_keeps_small_image_size(self):
        cleaned = strip_image_metadata(io.BytesIO(image_bytes((40, 30))))
        with opened(cleaned) as result:
            self.assertEqual(result.size, (40, 30))

    def test_strip_image_metadata_rejects_too_many_pixels_before_decoding(self):
        # 4001x4000 = 16 004 000 Pixel > 16 MP. Die Bilddaten werden
        # abgeschnitten: Würde dekodiert, käme "truncated" mit der
        # Standardmeldung – die Pixelmeldung beweist, dass nur der Header
        # gelesen wurde.
        full = image_bytes((4001, 4000), mode="L", color=0)
        header_and_some_data = full[:200]

        with self.assertRaises(InvalidAvatarImage) as ctx:
            strip_image_metadata(io.BytesIO(header_and_some_data))

        self.assertIn("слишком большое", ctx.exception.user_message)
        self.assertIn("16 мегапикселей", ctx.exception.user_message)

    def test_strip_image_metadata_accepts_exactly_max_pixels(self):
        # Grenzwert: 4000x4000 = 16 000 000 ist erlaubt (Vergleich mit ">").
        source = image_bytes((4000, 4000), mode="L", color=0)
        cleaned = strip_image_metadata(io.BytesIO(source))
        with opened(cleaned) as result:
            self.assertEqual(result.size, (MAX_AVATAR_EDGE, MAX_AVATAR_EDGE))
        self.assertEqual(MAX_AVATAR_PIXELS, 4000 * 4000)

    def test_strip_image_metadata_treats_decompression_bomb_warning_as_error(self):
        # Pillow warnt ab MAX_IMAGE_PIXELS (hier 100) und bricht erst ab dem
        # Doppelten ab. 12x10 = 120 Pixel liegt dazwischen → nur Warnung,
        # die trotzdem zum Fehler werden muss.
        source = image_bytes((12, 10))
        with mock.patch.object(Image, "MAX_IMAGE_PIXELS", 100):
            with self.assertRaises(InvalidAvatarImage) as ctx:
                strip_image_metadata(io.BytesIO(source))
        self.assertTrue(ctx.exception.user_message)

    def test_strip_image_metadata_keeps_palette_png_transparency(self):
        image = Image.new("P", (4, 4), 0)
        image.putpalette([0, 0, 0, 255, 0, 0] + [0] * (256 * 3 - 6))
        image.putpixel((1, 1), 1)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", transparency=0)

        cleaned = strip_image_metadata(io.BytesIO(buffer.getvalue()))

        self.assertEqual(cleaned.name, "avatar.png")
        with opened(cleaned) as result:
            self.assertEqual(result.format, "PNG")
            self.assertIn("transparency", result.info)
            # Pixel 0 transparent, Pixel (1,1) deckend rot.
            rgba = result.convert("RGBA")
            self.assertEqual(rgba.getpixel((0, 0))[3], 0)
            self.assertEqual(rgba.getpixel((1, 1)), (255, 0, 0, 255))

    def test_strip_image_metadata_rejects_gif(self):
        # Nicht mehr auf der Allowlist (früher als JPEG neu geschrieben).
        source = image_bytes((4, 4), mode="P", color=1, image_format="GIF")

        with self.assertRaises(InvalidAvatarImage) as ctx:
            strip_image_metadata(io.BytesIO(source))

        self.assertEqual(
            ctx.exception.user_message, "Поддерживаются только JPEG, PNG и WebP."
        )

    def test_strip_image_metadata_keeps_webp_format(self):
        source = image_bytes((4, 4), image_format="WEBP")
        cleaned = strip_image_metadata(io.BytesIO(source))
        self.assertEqual(cleaned.name, "avatar.webp")

    def test_strip_image_metadata_rejects_non_image(self):
        with self.assertRaises(InvalidAvatarImage) as ctx:
            strip_image_metadata(io.BytesIO(b"%PDF-1.4 kein Bild"))
        self.assertIn("JPEG, PNG и WebP", ctx.exception.user_message)

    def test_strip_image_metadata_rejects_empty_file(self):
        with self.assertRaises(InvalidAvatarImage):
            strip_image_metadata(io.BytesIO(b""))


AVATAR_URL = "/api/v1/profiles/user/me/avatar/"
AVATAR_ORIGINAL_URL = "/api/v1/profiles/user/me/avatar/original/"


@override_settings(CACHES=LOCMEM_CACHE)
class AvatarUploadTestBase(TempMediaRootMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.invite_delay = mock.patch(
            "apps.bot.tasks.email.send_telegram_invite_email.delay"
        ).start()
        self.sync_post = mock.patch(
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
        self.profile = MemberProfile(user=self.user, **COMPLETE_PROFILE)
        self.profile.ensure_unique_slug()
        self.profile.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def upload(self, **extra):
        payload = {"avatar": image_upload(), **extra}
        return self.client.post(AVATAR_URL, payload, format="multipart")


class AvatarUploadValidationTests(AvatarUploadTestBase):
    def test_avatar_upload_rejects_file_over_five_megabytes(self):
        too_large = SimpleUploadedFile(
            "avatar.jpg", b"\0" * (MAX_AVATAR_UPLOAD_BYTES + 1), "image/jpeg"
        )
        response = self.client.post(
            AVATAR_URL, {"avatar": too_large}, format="multipart"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            [str(m) for m in response.data["avatar"]],
            ["Файл слишком большой. Максимум – 5 МБ."],
        )

    def test_avatar_upload_rejects_non_image_with_russian_message(self):
        not_an_image = SimpleUploadedFile("avatar.png", b"kein Bild", "image/png")
        response = self.client.post(
            AVATAR_URL, {"avatar": not_an_image}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("avatar", response.data)

    def test_avatar_upload_stores_cleaned_file_under_random_name(self):
        upload = SimpleUploadedFile(
            "user-1.jpg", jpeg_with_gps_and_xmp(), content_type="image/jpeg"
        )
        response = self.client.post(AVATAR_URL, {"avatar": upload}, format="multipart")

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertRegex(self.profile.avatar.name, r"^avatars/[0-9a-f]{32}\.jpg$")
        with self.profile.avatar.open("rb") as handle:
            stored = handle.read()
        self.assertNotIn(b"geheimer-standort", stored)
        with Image.open(io.BytesIO(stored)) as result:
            self.assertEqual(dict(result.getexif()), {})


class AvatarUploadThrottleTests(AvatarUploadTestBase):
    def test_avatar_upload_is_throttled_by_own_scope(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"avatar": "2/hour"}):
            statuses = [self.upload().status_code for _ in range(3)]

        self.assertEqual(statuses, [200, 200, 429])

    def test_avatar_throttle_does_not_limit_profile_reads(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"avatar": "1/hour"}):
            self.upload()
            self.assertEqual(self.upload().status_code, 429)
            response = self.client.get("/api/v1/profiles/user/me/")
        self.assertEqual(response.status_code, 200)


class AvatarUploadPersistenceTests(AvatarUploadTestBase):
    def test_avatar_upload_does_not_overwrite_concurrent_profile_change(self):
        """
        Ein paralleler PATCH ändert city, nachdem der Upload das Profil
        gelesen hat. update_fields darf den alten Stand nicht zurückschreiben.
        """
        original = MemberProfile.avatar_file_names
        calls = []

        def concurrent_patch(profile):
            if not calls:
                MemberProfile.objects.filter(pk=profile.pk).update(city="Hamburg")
            calls.append(profile.pk)
            return original(profile)

        with mock.patch.object(
            MemberProfile,
            "avatar_file_names",
            autospec=True,
            side_effect=concurrent_patch,
        ):
            response = self.upload(avatar_scale="1.5")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(calls, "Der simulierte parallele Schreibzugriff lief nie.")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.city, "Hamburg")
        self.assertTrue(self.profile.avatar)
        self.assertEqual(self.profile.avatar_scale, 1.5)

    def test_avatar_upload_keeps_text_fields(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        for name, value in COMPLETE_PROFILE.items():
            with self.subTest(field=name):
                self.assertEqual(getattr(self.profile, name), value)

    def test_avatar_upload_completing_profile_sends_invite_exactly_once(self):
        # Alle Textpflichtfelder sind gefüllt, nur der Avatar fehlt → der
        # erste Upload ist die Flanke, der zweite nicht mehr.
        first = self.upload()
        second = self.upload()

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["directory_ready"])
        self.assertEqual(first.data["missing_fields"], [])
        self.assertEqual(second.status_code, 200)
        self.invite_delay.assert_called_once_with(self.user.pk)
        # Der Profilpost wird bei jedem Upload angestoßen.
        self.assertEqual(self.sync_post.call_count, 2)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_directory_visible)

    def test_avatar_upload_on_incomplete_profile_sends_no_invite(self):
        MemberProfile.objects.filter(pk=self.profile.pk).update(bio="")

        response = self.upload()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["directory_ready"])
        self.assertEqual(response.data["missing_fields"], ["bio"])
        self.invite_delay.assert_not_called()

    def test_avatar_upload_response_has_no_original_url(self):
        response = self.upload(avatar_original=image_upload("orig.png"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_avatar_original"])
        self.assertFalse(any("original_url" in key for key in response.data))


class AvatarReplacementCleanupTests(AvatarUploadTestBase):
    def setUp(self):
        super().setUp()
        response = self.upload(avatar_original=image_upload("orig.png"))
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.old_files = self.profile.avatar_file_names()
        self.assertEqual(len(self.old_files), 2)

    def test_replaced_files_are_deleted_only_after_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.upload(avatar_original=image_upload("orig.png"))
        self.assertEqual(response.status_code, 200)

        # Vor dem Commit verweist die DB-Zeile anderer Leser noch auf sie.
        for name in self.old_files:
            self.assertTrue(default_storage.exists(name), name)

        for callback in callbacks:
            callback()

        for name in self.old_files:
            self.assertFalse(default_storage.exists(name), name)
        self.profile.refresh_from_db()
        new_files = self.profile.avatar_file_names()
        self.assertFalse(new_files & self.old_files)
        for name in new_files:
            self.assertTrue(default_storage.exists(name), name)

    def test_avatar_only_upload_keeps_existing_original(self):
        old_original = self.profile.avatar_original.name

        with self.captureOnCommitCallbacks(execute=True):
            response = self.upload()

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_original.name, old_original)
        self.assertTrue(default_storage.exists(old_original))
        self.assertFalse(
            default_storage.exists(next(iter(self.old_files - {old_original})))
        )

    def test_replaced_files_survive_rollback(self):
        with self.captureOnCommitCallbacks(execute=True):
            with mock.patch.object(
                MemberProfile,
                "refresh_directory_visibility",
                side_effect=RuntimeError("DB weg"),
            ):
                with self.assertRaises(RuntimeError):
                    self.upload(avatar_original=image_upload("orig.png"))

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_file_names(), self.old_files)
        for name in self.old_files:
            self.assertTrue(default_storage.exists(name), name)


async def collect_async_stream(response) -> bytes:
    return b"".join([chunk async for chunk in response.streaming_content])


class AvatarOriginalEndpointTests(AvatarUploadTestBase):
    def test_avatar_original_requires_authentication(self):
        response = APIClient().get(AVATAR_ORIGINAL_URL)
        self.assertEqual(response.status_code, 401)

    def test_avatar_original_without_original_returns_404(self):
        response = self.client.get(AVATAR_ORIGINAL_URL)
        self.assertEqual(response.status_code, 404)

    def test_avatar_original_with_missing_file_returns_404(self):
        MemberProfile.objects.filter(pk=self.profile.pk).update(
            avatar_original=f"{AVATAR_ORIGINALS_DIR}/{'0' * 32}.png"
        )
        response = self.client.get(AVATAR_ORIGINAL_URL)
        self.assertEqual(response.status_code, 404)

    def test_avatar_original_streams_file_privately(self):
        self.upload(avatar_original=image_upload("orig.png", size=(30, 20)))
        self.profile.refresh_from_db()
        with self.profile.avatar_original.open("rb") as handle:
            expected = handle.read()

        response = self.client.get(AVATAR_ORIGINAL_URL)

        self.assertEqual(response.status_code, 200)
        # Async-Iterator: Unter ASGI wird blockweise gestreamt, nicht vorab
        # komplett in den Speicher gelesen.
        self.assertTrue(response.streaming)
        self.assertTrue(response.is_async)
        body = async_to_sync(collect_async_stream)(response)
        self.assertEqual(body, expected)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Content-Length"], str(len(expected)))
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_avatar_original_returns_only_own_original(self):
        self.upload(avatar_original=image_upload("orig.png"))
        other = CustomUser.objects.create_user(
            email="boris@example.com",
            password="Str0ng!Passwort",
            first_name="Boris",
            last_name="C",
            is_active=True,
        )
        client = APIClient()
        client.force_authenticate(other)

        response = client.get(AVATAR_ORIGINAL_URL)

        self.assertEqual(response.status_code, 404)

    def test_public_profile_exposes_no_avatar_original(self):
        self.upload(avatar_original=image_upload("orig.png"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_directory_visible)

        response = self.client.get(f"/api/v1/profiles/{self.profile.slug}/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(any("original" in key for key in response.data))
        self.assertNotIn(self.profile.avatar_original.name, str(response.data))


class AnonymizeAvatarFilesTests(TempMediaRootMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        self.profile = MemberProfile(user=self.user, **COMPLETE_PROFILE)
        self.profile.avatar.save("a.png", one_pixel_png(), save=False)
        self.profile.avatar_original.save("o.png", one_pixel_png(), save=False)
        self.profile.ensure_unique_slug()
        self.profile.save()
        self.files = self.profile.avatar_file_names()

    def test_anonymize_deletes_files_only_after_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.profile.anonymize()

        for name in self.files:
            self.assertTrue(default_storage.exists(name), name)
        for callback in callbacks:
            callback()
        for name in self.files:
            self.assertFalse(default_storage.exists(name), name)

    def test_anonymize_rollback_keeps_files(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self.profile.anonymize()
                    raise RuntimeError("Kontolöschung bricht ab")

        for name in self.files:
            self.assertTrue(default_storage.exists(name), name)

    def test_anonymize_does_not_scan_avatar_directory(self):
        # Altlasten räumt cleanup_legacy_avatars auf – anonymize() darf das
        # Verzeichnis nicht mehr durchsuchen, und fremde Dateien bleiben.
        default_storage.save(f"{AVATAR_DIR}/user-{self.user.pk}.jpg", one_pixel_png())
        with mock.patch(
            "django.core.files.storage.FileSystemStorage.listdir"
        ) as listdir:
            with self.captureOnCommitCallbacks(execute=True):
                self.profile.anonymize()

        listdir.assert_not_called()
        self.assertTrue(default_storage.exists(f"{AVATAR_DIR}/user-{self.user.pk}.jpg"))


def legacy_jpeg(color=(10, 200, 10)) -> bytes:
    exif = Image.Exif()
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (53.0, 4.0, 30.0)
    return image_bytes((6, 6), color=color, image_format="JPEG", exif=exif.tobytes())


def save_exact(name: str, content: bytes) -> str:
    stored = default_storage.save(name, ContentFile(content))
    assert stored == name, f"Storage hat {name} zu {stored} umbenannt"
    return stored


def mean_color(data: bytes) -> tuple[int, ...]:
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGB").resize((1, 1)).getpixel((0, 0))


class CleanupLegacyAvatarsTestBase(TempMediaRootMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.invite_delay = mock.patch(
            "apps.bot.tasks.email.send_telegram_invite_email.delay"
        ).start()
        self.sync_post = mock.patch(
            "apps.bot.tasks.profile_post.sync_telegram_profile_post.delay"
        ).start()
        self.addCleanup(mock.patch.stopall)

    def make_profile(self, email: str, *, visible: bool = False, **fields):
        user = CustomUser.objects.create_user(
            email=email,
            password="Str0ng!Passwort",
            first_name=email.split("@")[0],
            last_name="X",
            is_active=True,
        )
        profile = MemberProfile(
            user=user, is_directory_visible=visible, **COMPLETE_PROFILE, **fields
        )
        profile.ensure_unique_slug()
        profile.save()
        return profile

    def run_cleanup(self, *args) -> str:
        out = io.StringIO()
        with self.captureOnCommitCallbacks(execute=True):
            call_command("cleanup_legacy_avatars", *args, stdout=out)
        return out.getvalue()


class CleanupLegacyAvatarsTests(CleanupLegacyAvatarsTestBase):
    def test_cleanup_rewrites_referenced_legacy_file_without_exif(self):
        old_avatar = save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg())
        old_original = save_exact(
            f"{AVATAR_ORIGINALS_DIR}/user-1_AbC123x.jpg", legacy_jpeg()
        )
        profile = self.make_profile(
            "anna@example.com", avatar=old_avatar, avatar_original=old_original
        )

        self.run_cleanup()

        profile.refresh_from_db()
        self.assertRegex(profile.avatar.name, r"^avatars/[0-9a-f]{32}\.jpg$")
        self.assertRegex(
            profile.avatar_original.name, r"^avatars/originals/[0-9a-f]{32}\.jpg$"
        )
        for field in (profile.avatar, profile.avatar_original):
            with field.open("rb") as handle, Image.open(handle) as image:
                self.assertEqual(dict(image.getexif()), {})
        self.assertFalse(default_storage.exists(old_avatar))
        self.assertFalse(default_storage.exists(old_original))

    def test_cleanup_deletes_old_file_only_after_commit(self):
        # Der Löschschritt für Unreferenziertes ist hier abgeschaltet: Im
        # TestCase laufen die on_commit-Callbacks erst am Ende, er fände die
        # umgeschriebene Altdatei sonst schon vorher als unreferenziert.
        old_avatar = save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg())
        profile = self.make_profile("anna@example.com", avatar=old_avatar)

        with mock.patch(
            "apps.profiles.legacy_avatars._delete_unreferenced_legacy_files"
        ):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                call_command("cleanup_legacy_avatars", stdout=io.StringIO())
            self.assertTrue(default_storage.exists(old_avatar))
            for callback in callbacks:
                callback()

        self.assertFalse(default_storage.exists(old_avatar))
        profile.refresh_from_db()
        self.assertTrue(default_storage.exists(profile.avatar.name))

    def test_cleanup_deletes_unreferenced_legacy_files_only(self):
        stale = {
            save_exact(f"{AVATAR_DIR}/user-999.jpg", legacy_jpeg()),
            save_exact(f"{AVATAR_DIR}/user-7_Xy12ab.png", one_pixel_png().read()),
            save_exact(f"{AVATAR_ORIGINALS_DIR}/user-5.jpg", legacy_jpeg()),
        }
        # Nicht im alten Schema: bleiben trotz fehlender Referenz liegen.
        kept = {
            save_exact(f"{AVATAR_DIR}/{'a' * 32}.jpg", legacy_jpeg()),
            save_exact(f"{AVATAR_DIR}/user-1-backup.jpg", legacy_jpeg()),
            save_exact(f"{AVATAR_DIR}/myuser-1.jpg", legacy_jpeg()),
        }

        output = self.run_cleanup()

        for name in stale:
            self.assertFalse(default_storage.exists(name), name)
            self.assertIn(f"Gelöscht: {name}", output)
        for name in kept:
            self.assertTrue(default_storage.exists(name), name)

    def test_cleanup_keeps_user_1_and_user_10_apart(self):
        # Rot für user-1, Blau für user-10: Nach dem Umschreiben muss jedes
        # Profil noch sein eigenes Bild tragen und keines gelöscht sein.
        red, blue = (220, 0, 0), (0, 0, 220)
        first = self.make_profile(
            "eins@example.com",
            avatar=save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg(red)),
        )
        tenth = self.make_profile(
            "zehn@example.com",
            avatar=save_exact(f"{AVATAR_DIR}/user-10.jpg", legacy_jpeg(blue)),
        )

        self.run_cleanup()

        first.refresh_from_db()
        tenth.refresh_from_db()
        self.assertNotEqual(first.avatar.name, tenth.avatar.name)
        with first.avatar.open("rb") as handle:
            r, g, b = mean_color(handle.read())
            self.assertGreater(r, 150)
            self.assertLess(b, 60)
        with tenth.avatar.open("rb") as handle:
            r, g, b = mean_color(handle.read())
            self.assertGreater(b, 150)
            self.assertLess(r, 60)

    def test_cleanup_clears_dead_references_without_side_effects(self):
        # Irgendeine Datei im Verzeichnis, sonst greift der Riegel gegen ein
        # fehlendes Media-Volume.
        save_exact(f"{AVATAR_DIR}/{'d' * 32}.jpg", legacy_jpeg())
        profile = self.make_profile(
            "anna@example.com",
            visible=True,
            avatar=f"{AVATAR_DIR}/{'b' * 32}.jpg",
            avatar_original=f"{AVATAR_ORIGINALS_DIR}/user-3.jpg",
        )

        output = self.run_cleanup("--clear-missing", "--force")

        profile.refresh_from_db()
        self.assertFalse(profile.avatar)
        self.assertFalse(profile.avatar_original)
        # Avatar ist Pflichtfeld → Profil fällt aus dem Verzeichnis.
        self.assertFalse(profile.is_directory_visible)
        self.assertIn(
            f"Nicht mehr im Verzeichnis sichtbar (Avatar fehlt): {profile.pk}", output
        )
        self.invite_delay.assert_not_called()
        self.sync_post.assert_not_called()

    def test_cleanup_keeps_existing_random_name_reference(self):
        name = save_exact(f"{AVATAR_DIR}/{'c' * 32}.jpg", legacy_jpeg())
        profile = self.make_profile("anna@example.com", visible=True, avatar=name)

        self.run_cleanup()

        profile.refresh_from_db()
        self.assertEqual(profile.avatar.name, name)
        self.assertTrue(profile.is_directory_visible)
        self.assertTrue(default_storage.exists(name))

    def test_cleanup_dry_run_changes_nothing(self):
        referenced = save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg())
        save_exact(f"{AVATAR_DIR}/user-999.jpg", legacy_jpeg())
        self.make_profile("anna@example.com", visible=True, avatar=referenced)
        dead = self.make_profile(
            "boris@example.com", visible=True, avatar=f"{AVATAR_DIR}/user-2.jpg"
        )
        files_before = self.storage_names()
        rows_before = list(
            MemberProfile.objects.order_by("pk").values(
                "pk", "avatar", "avatar_original", "is_directory_visible"
            )
        )

        output = self.run_cleanup("--dry-run")

        self.assertEqual(self.storage_names(), files_before)
        self.assertEqual(
            list(
                MemberProfile.objects.order_by("pk").values(
                    "pk", "avatar", "avatar_original", "is_directory_visible"
                )
            ),
            rows_before,
        )
        self.assertIn("[Dry-Run]", output)
        self.assertIn(f"Umgeschrieben: {referenced} -> <Zufallsname>", output)
        self.assertIn(f"Gelöscht: {AVATAR_DIR}/user-999.jpg", output)
        self.assertIn(f"Profil {dead.pk}: avatar zeigt auf fehlende", output)
        self.assertNotIn(f"Gelöscht: {referenced}", output)

    def test_cleanup_second_run_is_idempotent(self):
        save_exact(f"{AVATAR_DIR}/user-999.jpg", legacy_jpeg())
        profile = self.make_profile(
            "anna@example.com",
            visible=True,
            avatar=save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg()),
        )
        self.make_profile("boris@example.com", avatar=f"{AVATAR_DIR}/user-2.jpg")

        self.run_cleanup()
        profile.refresh_from_db()
        files_after_first = self.storage_names()
        avatar_after_first = profile.avatar.name

        output = self.run_cleanup()

        profile.refresh_from_db()
        self.assertEqual(profile.avatar.name, avatar_after_first)
        self.assertEqual(self.storage_names(), files_after_first)
        self.assertIn(
            "Avatar-Altlasten: 0 Verweise geleert, 0 Dateien umgeschrieben, "
            "0 unverändert verschoben, 0 gelöscht, 0 Fehler, "
            "1 tote Verweise gefunden.",
            output,
        )

    def test_cleanup_moves_unreadable_legacy_file_to_random_name(self):
        broken = save_exact(f"{AVATAR_DIR}/user-4.jpg", b"kein Bild")
        profile = self.make_profile("anna@example.com", avatar=broken)

        output = self.run_cleanup()

        profile.refresh_from_db()
        self.assertRegex(profile.avatar.name, r"^avatars/[0-9a-f]{32}\.jpg$")
        with profile.avatar.open("rb") as handle:
            self.assertEqual(handle.read(), b"kein Bild")
        self.assertFalse(default_storage.exists(broken))
        self.assertIn(
            f"Nicht lesbar, unverändert verschoben: {broken} -> {profile.avatar.name}",
            output,
        )


# --- Cleanup: Riegel gegen fehlendes Media-Volume und tote Verweise ------ #


def random_avatar_name(char: str, *, ext: str = "jpg") -> str:
    """Name im aktuellen Schema (32 Hex-Zeichen), kein Altlast-Name."""
    return f"{AVATAR_DIR}/{char * 32}.{ext}"


class CleanupLegacyAvatarsGuardTests(CleanupLegacyAvatarsTestBase):
    def profile_rows(self) -> list[dict]:
        return list(
            MemberProfile.objects.order_by("pk").values(
                "pk", "avatar", "avatar_original", "is_directory_visible"
            )
        )

    def assert_aborted_without_changes(self, *args) -> None:
        rows_before = self.profile_rows()
        files_before = self.storage_names()

        with self.assertRaises(CommandError):
            self.run_cleanup(*args)

        self.assertEqual(self.profile_rows(), rows_before)
        self.assertEqual(self.storage_names(), files_before)

    def test_cleanup_aborts_when_avatar_directory_is_missing(self):
        # Verweise in der DB, aber MEDIA_ROOT/avatars existiert gar nicht –
        # typisch für ein nicht gemountetes Volume.
        self.make_profile(
            "anna@example.com", visible=True, avatar=random_avatar_name("a")
        )
        self.make_profile("boris@example.com", avatar=f"{AVATAR_DIR}/user-2.jpg")

        for args in ((), ("--clear-missing",), ("--clear-missing", "--force")):
            with self.subTest(args=args):
                self.assert_aborted_without_changes(*args)

    def test_cleanup_aborts_when_avatar_directory_is_empty(self):
        os.makedirs(default_storage.path(AVATAR_ORIGINALS_DIR))
        self.make_profile(
            "anna@example.com", visible=True, avatar=random_avatar_name("a")
        )

        for args in ((), ("--clear-missing", "--force")):
            with self.subTest(args=args):
                self.assert_aborted_without_changes(*args)

    def test_cleanup_without_references_and_files_is_a_no_op(self):
        # Kein Verweis → kein Riegel (frische Installation).
        output = self.run_cleanup("--clear-missing")
        self.assertIn("0 tote Verweise gefunden.", output)

    def test_cleanup_aborts_clear_missing_above_ratio_without_force(self):
        # 1 von 2 Verweisen tot = 50 % > 20 %.
        self.make_profile(
            "anna@example.com",
            visible=True,
            avatar=save_exact(random_avatar_name("a"), legacy_jpeg()),
        )
        self.make_profile(
            "boris@example.com", visible=True, avatar=random_avatar_name("b")
        )

        self.assert_aborted_without_changes("--clear-missing")

    def test_cleanup_clears_above_ratio_with_force(self):
        self.make_profile(
            "anna@example.com",
            visible=True,
            avatar=save_exact(random_avatar_name("a"), legacy_jpeg()),
        )
        dead = self.make_profile(
            "boris@example.com", visible=True, avatar=random_avatar_name("b")
        )

        output = self.run_cleanup("--clear-missing", "--force")

        dead.refresh_from_db()
        self.assertFalse(dead.avatar)
        self.assertFalse(dead.is_directory_visible)
        self.assertIn(
            f"Profil {dead.pk}: avatar zeigt auf fehlende Datei, geleert.", output
        )

    def test_cleanup_clears_exactly_at_ratio_without_force(self):
        # 1 von 5 Verweisen tot = genau 20 % → noch plausibel, kein --force nötig.
        for index, char in enumerate("acde"):
            self.make_profile(
                f"p{index}@example.com",
                avatar=save_exact(random_avatar_name(char), legacy_jpeg()),
            )
        dead = self.make_profile("boris@example.com", avatar=random_avatar_name("b"))

        self.run_cleanup("--clear-missing")

        dead.refresh_from_db()
        self.assertFalse(dead.avatar)

    def test_cleanup_without_clear_missing_keeps_dead_reference(self):
        save_exact(random_avatar_name("a"), legacy_jpeg())
        dead_name = random_avatar_name("b")
        dead = self.make_profile("boris@example.com", visible=True, avatar=dead_name)

        output = self.run_cleanup()

        dead.refresh_from_db()
        self.assertEqual(dead.avatar.name, dead_name)
        self.assertTrue(dead.is_directory_visible)
        self.assertIn(
            f"Profil {dead.pk}: avatar zeigt auf fehlende Datei, "
            "nicht geleert (dafür --clear-missing).",
            output,
        )


class CleanupLegacyAvatarsPerFileTests(CleanupLegacyAvatarsTestBase):
    def test_cleanup_reference_outside_media_root_is_reported_and_run_continues(self):
        evil = self.make_profile("eve@example.com")
        MemberProfile.objects.filter(pk=evil.pk).update(avatar="../geheim.jpg")
        legacy = self.make_profile(
            "anna@example.com",
            avatar=save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg()),
        )

        output = self.run_cleanup("--clear-missing", "--force")

        evil.refresh_from_db()
        legacy.refresh_from_db()
        self.assertEqual(evil.avatar.name, "../geheim.jpg")
        self.assertIn("Fehler, unverändert: ../geheim.jpg", output)
        # Der Lauf ging weiter: Die Altdatei des anderen Profils ist umgeschrieben.
        self.assertRegex(legacy.avatar.name, r"^avatars/[0-9a-f]{32}\.jpg$")

    def test_cleanup_moves_gif_legacy_file_unchanged_and_deletes_old_after_commit(self):
        # GIF ist nicht auf der Allowlist → nicht umschreibbar, aber auch
        # nicht unter dem erratbaren Namen liegen lassen.
        gif = image_bytes((4, 4), mode="P", color=1, image_format="GIF")
        old_name = save_exact(f"{AVATAR_DIR}/user-5.gif", gif)
        profile = self.make_profile("anna@example.com", avatar=old_name)

        out = io.StringIO()
        # Löschschritt für Unreferenziertes aus wie in
        # test_cleanup_deletes_old_file_only_after_commit.
        with mock.patch(
            "apps.profiles.legacy_avatars._delete_unreferenced_legacy_files"
        ):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                call_command("cleanup_legacy_avatars", stdout=out)
            self.assertTrue(default_storage.exists(old_name))
            for callback in callbacks:
                callback()

        profile.refresh_from_db()
        self.assertRegex(profile.avatar.name, r"^avatars/[0-9a-f]{32}\.[a-z]+$")
        with profile.avatar.open("rb") as handle:
            self.assertEqual(handle.read(), gif)
        self.assertFalse(default_storage.exists(old_name))
        self.assertIn(
            f"Nicht lesbar, unverändert verschoben: {old_name} -> {profile.avatar.name}",
            out.getvalue(),
        )

    def test_cleanup_storage_write_error_keeps_reference(self):
        old_name = save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg())
        profile = self.make_profile("anna@example.com", avatar=old_name)

        with mock.patch.object(
            FileSystemStorage, "_save", side_effect=OSError("Platte voll")
        ):
            output = self.run_cleanup()

        profile.refresh_from_db()
        self.assertEqual(profile.avatar.name, old_name)
        self.assertTrue(default_storage.exists(old_name))
        self.assertIn(f"Fehler, unverändert: {old_name}", output)
        self.assertIn("0 Dateien umgeschrieben", output)

    def test_cleanup_storage_read_error_keeps_reference(self):
        old_name = save_exact(f"{AVATAR_DIR}/user-1.jpg", legacy_jpeg())
        profile = self.make_profile("anna@example.com", avatar=old_name)

        with mock.patch.object(
            FileSystemStorage, "open", side_effect=PermissionError("kein Zugriff")
        ):
            output = self.run_cleanup()

        profile.refresh_from_db()
        self.assertEqual(profile.avatar.name, old_name)
        self.assertTrue(default_storage.exists(old_name))
        self.assertIn(f"Fehler, unverändert: {old_name}", output)


# --- Upload: Format-Allowlist, Pillow-Fehler, Rollback ------------------- #

DEFAULT_INVALID_IMAGE_FRAGMENT = "Не удалось обработать изображение"


class AvatarUploadFormatTests(AvatarUploadTestBase):
    def post_avatar(self, content: bytes, name: str = "avatar.png"):
        upload = SimpleUploadedFile(name, content, content_type="image/png")
        return self.client.post(AVATAR_URL, {"avatar": upload}, format="multipart")

    def assert_rejected(self, response, message_fragment: str) -> None:
        self.assertEqual(response.status_code, 400)
        messages = [str(m) for m in response.data["avatar"]]
        self.assertEqual(len(messages), 1)
        self.assertIn(message_fragment, messages[0])
        self.assertEqual(self.storage_names(), set())
        self.invite_delay.assert_not_called()

    def test_avatar_upload_rejects_foreign_formats_before_pillow(self):
        # Signaturprüfung vor jedem Parser: Pillow darf die Datei nie sehen,
        # auch wenn der Name .png behauptet.
        for image_format in ("GIF", "BMP", "TIFF"):
            with self.subTest(image_format=image_format):
                content = image_bytes((4, 4), image_format=image_format)
                with mock.patch("PIL.Image.open", wraps=Image.open) as image_open:
                    response = self.post_avatar(content)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    [str(m) for m in response.data["avatar"]],
                    [UNSUPPORTED_FORMAT_MESSAGE],
                )
                self.assertEqual(
                    UNSUPPORTED_FORMAT_MESSAGE,
                    "Поддерживаются только JPEG, PNG и WebP.",
                )
                image_open.assert_not_called()

    def test_avatar_upload_accepts_webp(self):
        response = self.post_avatar(
            image_bytes((4, 4), image_format="WEBP"), name="avatar.webp"
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertRegex(self.profile.avatar.name, r"^avatars/[0-9a-f]{32}\.webp$")
        with self.profile.avatar.open("rb") as handle, Image.open(handle) as image:
            self.assertEqual(image.format, "WEBP")

    def test_avatar_upload_rejects_crafted_files_with_400(self):
        jpeg = image_bytes((64, 64), image_format="JPEG")
        crafted = {
            "png_signature_garbage": b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
            "jpeg_signature_garbage": b"\xff\xd8\xff" + b"\x13" * 64,
            "webp_signature_garbage": b"RIFF\x10\x00\x00\x00WEBP" + b"\x00" * 32,
            "truncated_jpeg": jpeg[: len(jpeg) // 2],
        }
        for label, content in crafted.items():
            with self.subTest(label):
                response = self.post_avatar(content)
                self.assertEqual(response.status_code, 400)
                self.assertIn("avatar", response.data)
                self.assertEqual(self.storage_names(), set())

    def test_avatar_upload_maps_pillow_decode_errors_to_400(self):
        # Parserfehler einzelner Pillow-Plugins sind keine OSError – ohne
        # vollständige Liste würde daraus ein 500.
        for error in (
            ValueError("kaputt"),
            EOFError(),
            struct.error("kaputt"),
            SyntaxError("kaputt"),
            IndexError("kaputt"),
        ):
            with self.subTest(error=type(error).__name__):
                with mock.patch(
                    "apps.profiles.avatar_files.ImageOps.exif_transpose",
                    side_effect=error,
                ):
                    response = self.upload()
                self.assert_rejected(response, DEFAULT_INVALID_IMAGE_FRAGMENT)

    def test_avatar_upload_maps_pillow_encode_error_to_400(self):
        # Upload vor dem Patch bauen – image_upload() kodiert selbst mit save().
        payload = {"avatar": image_upload()}
        with mock.patch.object(
            Image.Image, "save", side_effect=ValueError("encoder kaputt")
        ):
            response = self.client.post(AVATAR_URL, payload, format="multipart")
        self.assert_rejected(response, DEFAULT_INVALID_IMAGE_FRAGMENT)

    def test_avatar_upload_too_many_pixels_keeps_specific_message(self):
        # 4001 × 4000 = 16 004 000 Pixel > 16 MP; einfarbig, also winzige Datei.
        content = image_bytes((4001, 4000), mode="L", color=0)
        self.assertLess(len(content), MAX_AVATAR_UPLOAD_BYTES)

        response = self.post_avatar(content)

        self.assert_rejected(response, "слишком большое")
        self.assertIn("16 мегапикселей", str(response.data["avatar"][0]))

    def test_avatar_upload_rejects_more_than_two_files(self):
        # DATA_UPLOAD_MAX_NUMBER_FILES = 2: Avatar + Original, nicht mehr.
        response = self.client.post(
            AVATAR_URL,
            {
                "avatar": image_upload(),
                "avatar_original": image_upload("orig.png"),
                "extra": image_upload("extra.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)
        self.assertEqual(self.storage_names(), set())


class AvatarUploadRollbackTests(AvatarUploadTestBase):
    def test_avatar_upload_failure_after_write_removes_new_files(self):
        with self.captureOnCommitCallbacks(execute=True):
            with mock.patch.object(
                MemberProfile,
                "refresh_directory_visibility",
                side_effect=RuntimeError("DB weg"),
            ):
                with self.assertRaises(RuntimeError):
                    self.upload(
                        avatar_original=image_upload("orig.png"), avatar_scale="2.0"
                    )

        # Beide Dateien waren schon geschrieben – ohne Aufräumen lägen sie
        # verwaist unter einer gültigen /media/-URL.
        self.assertEqual(self.storage_names(), set())
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)
        self.assertFalse(self.profile.avatar_original)
        self.assertEqual(self.profile.avatar_scale, 1.0)
        self.invite_delay.assert_not_called()

    def test_avatar_upload_failing_second_write_removes_first_file(self):
        real_save = FileSystemStorage._save
        calls = []

        def fail_on_second(storage, name, content):
            calls.append(name)
            if len(calls) == 2:
                raise OSError("Platte voll")
            return real_save(storage, name, content)

        with self.captureOnCommitCallbacks(execute=True):
            with mock.patch.object(
                FileSystemStorage, "_save", autospec=True, side_effect=fail_on_second
            ):
                with self.assertRaises(OSError):
                    self.upload(avatar_original=image_upload("orig.png"))

        self.assertEqual(len(calls), 2)
        self.assertEqual(self.storage_names(), set())
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)


# --- PATCH /me/: keine verlorenen Avatar-Wechsel, Invite-Flanke ---------- #

PROFILE_ME_URL = "/api/v1/profiles/user/me/"


class ProfilePatchConcurrencyTests(AvatarUploadTestBase):
    def test_patch_does_not_revert_concurrent_avatar_change(self):
        """
        Ein Upload schreibt einen neuen Avatar, nachdem der PATCH das Profil
        geladen hat. Der PATCH darf den alten Verweis nicht zurückschreiben.
        """
        self.assertEqual(self.upload().status_code, 200)
        concurrent_name = random_avatar_name("e", ext="png")
        real_load = profile_views.aget_or_create_profile

        async def load_then_concurrent_upload(user):
            profile = await real_load(user)
            await sync_to_async(MemberProfile.objects.filter(pk=profile.pk).update)(
                avatar=concurrent_name
            )
            return profile

        with mock.patch.object(
            profile_views,
            "aget_or_create_profile",
            side_effect=load_then_concurrent_upload,
        ):
            response = self.client.patch(
                PROFILE_ME_URL, {"city": "Hamburg"}, format="json"
            )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar.name, concurrent_name)
        self.assertEqual(self.profile.city, "Hamburg")

    def test_patch_never_writes_avatar_fields(self):
        self.assertEqual(self.upload().status_code, 200)
        real_save = MemberProfile.save
        update_fields_seen = []

        def spy_save(profile, *args, **kwargs):
            update_fields_seen.append(kwargs.get("update_fields"))
            return real_save(profile, *args, **kwargs)

        with mock.patch.object(
            MemberProfile, "save", autospec=True, side_effect=spy_save
        ):
            response = self.client.patch(
                PROFILE_ME_URL,
                {"city": "Hamburg", "bio": "", "headline": "Neu"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(update_fields_seen)
        for update_fields in update_fields_seen:
            # Kein voller save(): der würde avatar/avatar_original mitschreiben.
            self.assertIsNotNone(update_fields)
            self.assertNotIn("avatar", update_fields)
            self.assertNotIn("avatar_original", update_fields)

    def test_patch_completing_profile_sends_invite_exactly_once(self):
        MemberProfile.objects.filter(pk=self.profile.pk).update(bio="")
        self.assertEqual(self.upload().status_code, 200)
        self.invite_delay.assert_not_called()
        self.sync_post.reset_mock()

        first = self.client.patch(PROFILE_ME_URL, {"bio": "Über mich"}, format="json")
        second = self.client.patch(PROFILE_ME_URL, {"bio": "Noch mehr"}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["directory_ready"])
        self.assertEqual(second.status_code, 200)
        self.invite_delay.assert_called_once_with(self.user.pk)
        self.assertEqual(self.sync_post.call_count, 2)
