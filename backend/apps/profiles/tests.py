import io
from unittest import mock

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.bot.models import TelegramInvite

from .hashtags import InvalidHashtag, normalize_hashtag, parse_hashtag
from .models import (
    DIRECTORY_REQUIRED_FIELDS,
    RESERVED_SLUGS,
    ContactMode,
    MemberProfile,
    ProfileTag,
)
from .serializers import MAX_PROFILE_TAGS
from .services import MAX_SUGGESTION_LIMIT
from .tag_vocabulary import INITIAL_PROFILE_TAGS
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
        self.assertEqual(
            [item["name"] for item in self.get("?q=Веб")], ["веб_разработка"]
        )
        self.assertEqual(
            [item["name"] for item in self.get("?q=веб_")], ["веб_разработка"]
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
        self.assertEqual(after_first, len(INITIAL_PROFILE_TAGS))

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
