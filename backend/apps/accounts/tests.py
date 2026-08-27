from unittest import mock

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import io

from PIL import Image

from apps.accounts.models import CustomUser
from apps.bot.exceptions import TelegramAPIError
from apps.bot.models import TelegramInvite
from apps.bot.services.telegram import find_invite_by_telegram_user_id
from apps.bot.tasks.account import purge_telegram_presence
from apps.bot.tasks.email import send_telegram_invite_email
from apps.profiles.models import ContactMode, ContactRequest, MemberProfile

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "throttle-tests",
    }
}

VALID_PASSWORD = "Str0ng!Passwort"


@override_settings(CACHES=LOCMEM_CACHE)
class ThrottleScopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def post_until_throttled(self, path: str, payload: dict, limit: int) -> int:
        """Feuert limit+1 Anfragen und gibt den letzten Statuscode zurück."""
        status_code = None
        for _ in range(limit + 1):
            status_code = self.client.post(path, payload, format="json").status_code
        return status_code

    def test_login_is_throttled_after_ten_attempts(self):
        status_code = self.post_until_throttled(
            "/api/v1/accounts/login/",
            {"email": "wer@example.com", "password": "falsch"},
            limit=10,
        )
        self.assertEqual(status_code, 429)

    def test_registration_is_throttled_after_five_attempts(self):
        status_code = self.post_until_throttled(
            "/api/v1/accounts/sign-up/",
            {"email": "a@example.com", "first_name": "A", "last_name": "B"},
            limit=5,
        )
        self.assertEqual(status_code, 429)

    def test_activation_is_throttled(self):
        status_code = self.post_until_throttled(
            "/api/v1/accounts/activate/",
            {"uid": "x", "token": "y"},
            limit=10,
        )
        self.assertEqual(status_code, 429)

    def test_password_reset_is_throttled(self):
        status_code = self.post_until_throttled(
            "/api/v1/accounts/password/reset/",
            {"email": "a@example.com"},
            limit=5,
        )
        self.assertEqual(status_code, 429)

    def test_activation_does_not_consume_password_reset_limit(self):

        for _ in range(10):
            self.client.post(
                "/api/v1/accounts/activate/",
                {"uid": "x", "token": "y"},
                format="json",
            )

        response = self.client.post(
            "/api/v1/accounts/password/reset/",
            {"email": "a@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_refresh_has_its_own_more_permissive_limit(self):
        """
        Der Refresh läuft automatisch aus dem Frontend und darf das
        Login Limit nicht verbrauchen.
        """
        for _ in range(11):
            self.client.post(
                "/api/v1/accounts/login/refresh/",
                {"refresh": "ungültig"},
                format="json",
            )

        response = self.client.post(
            "/api/v1/accounts/login/refresh/",
            {"refresh": "ungültig"},
            format="json",
        )
        self.assertNotEqual(response.status_code, 429)


@override_settings(CACHES=LOCMEM_CACHE)
class AuthenticatedThrottleTests(TestCase):
    """
    Kontoaktionen werden pro User-ID gezählt, nicht pro IP.
    """

    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password=VALID_PASSWORD,
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        self.client.force_authenticate(self.user)

    def test_password_change_is_throttled(self):
        status_code = None
        for _ in range(21):
            status_code = self.client.post(
                "/api/v1/accounts/password/change/",
                {
                    "current_password": "falsch",
                    "new_password": VALID_PASSWORD,
                    "new_password_confirm": VALID_PASSWORD,
                },
                format="json",
            ).status_code
        self.assertEqual(status_code, 429)

    def test_own_data_reading_is_not_throttled(self):
        """
        Bewusste Ausnahme: /user/me/ läuft bei jedem Seitenaufruf.
        """
        for _ in range(30):
            response = self.client.get("/api/v1/accounts/user/me/")
        self.assertEqual(response.status_code, 200)


COMPLETE_PROFILE_PAYLOAD = {
    "city": "Berlin",
    "headline": "Designerin",
    "bio": "Kurz über mich",
    "can_help_with": "Design-Reviews",
    "looking_for": "Sparring zu UX",
}


@override_settings(CACHES=LOCMEM_CACHE)
class InviteGateTests(TestCase):
    """
    Die Einladung ist der einzige Schritt im Onboarding, der sich nicht
    zurücknehmen lässt: Ein versandter Link ist einmalig gültig und
    wanderfähig. Diese Tests sichern, dass er genau einmal und nur mit
    vollständigem Profil hinausgeht.
    """

    def setUp(self):
        cache.clear()

        # Der Einladungs-Task läuft inline: Geprüft werden soll die ganze Kette
        # – PATCH => Flanke => Task => Mail.
        self.invite_delay = mock.patch(
            "apps.bot.tasks.email.send_telegram_invite_email.delay",
            side_effect=send_telegram_invite_email,
        ).start()

        self.create_link = mock.patch(
            "apps.bot.tasks.email.create_single_use_invite_link",
            return_value="https://t.me/+abc123",
        ).start()
        self.sync_post = mock.patch(
            "apps.bot.tasks.profile_post.sync_telegram_profile_post.delay"
        ).start()
        self.reminder = mock.patch(
            "apps.bot.tasks.profile_post.send_profile_completion_reminder.apply_async"
        ).start()
        self.addCleanup(mock.patch.stopall)

        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password=VALID_PASSWORD,
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        TelegramInvite.objects.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def invite(self) -> TelegramInvite:
        return TelegramInvite.objects.get(user=self.user)

    def patch_profile(self, **fields):
        return self.client.patch("/api/v1/profiles/user/me/", fields, format="json")

    def complete_profile(self):
        """
        Füllt alle Pflichtfelder inklusive Avatar.
        """
        self.patch_profile(**COMPLETE_PROFILE_PAYLOAD)
        profile = MemberProfile.objects.get(user=self.user)
        profile.avatar = "avatars/user-1.jpg"
        profile.save(update_fields=["avatar"])
        return profile

    # --- Das Gate ---------------------------------------------------------

    def test_incomplete_profile_does_not_receive_an_invitation(self):
        self.patch_profile(city="Berlin", headline="Designerin")
        self.assertIsNone(self.invite().invite_sent_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_activation_alone_does_not_trigger_an_invitation(self):
        """Der Kern des Umbaus: Vorher ging die Mail hier raus."""
        pending = CustomUser.objects.create_user(
            email="neu@example.com",
            password=VALID_PASSWORD,
            first_name="Boris",
            last_name="C",
            is_active=False,
        )
        response = self.client.post(
            "/api/v1/accounts/activate/",
            {
                "uid": urlsafe_base64_encode(force_bytes(pending.pk)),
                "token": default_token_generator.make_token(pending),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertTrue(pending.is_active)
        # --- Invite-Zeile ja, Versand nein.
        self.assertTrue(TelegramInvite.objects.filter(user=pending).exists())
        self.assertIsNone(TelegramInvite.objects.get(user=pending).invite_sent_at)
        self.create_link.assert_not_called()

    def test_task_called_directly_checks_the_gate_itself(self):
        send_telegram_invite_email(self.user.pk)
        self.assertIsNone(self.invite().invite_sent_at)
        self.create_link.assert_not_called()

    def test_complete_profile_triggers_invitation(self):
        self.complete_profile()
        self.patch_profile(bio="Kurz über mich, ergänzt")

        invite = self.invite()
        self.assertIsNotNone(invite.invite_sent_at)
        self.assertEqual(invite.invite_link, "https://t.me/+abc123")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Telegram", mail.outbox[0].subject)

    def test_avatar_upload_as_the_last_required_field_cancels_the_invitation(self):
        self.patch_profile(**COMPLETE_PROFILE_PAYLOAD)
        self.assertIsNone(self.invite().invite_sent_at)

        response = self.client.post(
            "/api/v1/profiles/user/me/avatar/",
            {"avatar": _one_pixel_png()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(self.invite().invite_sent_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_save_second_does_not_trigger_a_second_invitation(self):
        self.complete_profile()
        self.patch_profile(bio="erste Fassung")
        self.assertEqual(len(mail.outbox), 1)

        self.patch_profile(bio="zweite Fassung")
        self.patch_profile(headline="neue Headline")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.create_link.call_count, 1)

    def test_task_is_idempotent_against_double_calls(self):
        """
        Schutz gegen Retries und parallele Tasks: invite_sent_at wird unter
        select_for_update gesetzt, bevor die Mail rausgeht.
        """
        self.complete_profile()
        send_telegram_invite_email(self.user.pk)
        send_telegram_invite_email(self.user.pk)
        send_telegram_invite_email(self.user.pk)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.create_link.call_count, 1)

    def test_inactive_account_does_not_receive_an_invitation(self):
        self.complete_profile()
        CustomUser.objects.filter(pk=self.user.pk).update(is_active=False)

        send_telegram_invite_email(self.user.pk)

        self.assertIsNone(self.invite().invite_sent_at)
        self.assertEqual(len(mail.outbox), 0)


def _one_pixel_png() -> SimpleUploadedFile:
    """
    Kleinstes gültiges PNG. ImageField verlangt ein von Pillow lesbares Bild.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(buffer, format="PNG")
    return SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png")


@override_settings(CACHES=LOCMEM_CACHE)
class AccountDeletionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.purge = mock.patch(
            "apps.bot.tasks.account.purge_telegram_presence.delay"
        ).start()
        self.addCleanup(mock.patch.stopall)

        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password=VALID_PASSWORD,
            first_name="Anna",
            last_name="B",
            is_active=True,
            street="Hauptstraße",
            street_no="1",
            zip_code="10115",
            city="Berlin",
        )
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
        )
        self.profile.avatar.save("user-x.png", _one_pixel_png(), save=False)
        self.profile.ensure_unique_slug()
        self.profile.save()

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def delete_account(self):
        return self.client.post(
            "/api/v1/accounts/delete/", {"password": VALID_PASSWORD}, format="json"
        )

    def test_incorrect_password_does_not_delete_anything(self):
        response = self.client.post(
            "/api/v1/accounts/delete/", {"password": "falsch"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_account_is_anonymized(self):
        self.assertEqual(self.delete_account().status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, f"deleted-{self.user.pk}@deleted.local")
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.has_usable_password())
        self.assertEqual(self.user.street, "")
        self.assertEqual(self.user.zip_code, "")
        self.assertEqual(self.user.city, "")

    def test_profile_contents_are_cleared(self):
        """Der Kern des Befunds: Vorher blieben Bio, Firma, Stadt, Handle und
        die URLs unangetastet stehen."""
        self.delete_account()
        self.profile.refresh_from_db()

        for field in (
            "headline",
            "city",
            "profession",
            "company",
            "position",
            "bio",
            "can_help_with",
            "looking_for",
            "telegram_username",
            "linkedin_url",
            "website_url",
            "telegram_group_url",
        ):
            with self.subTest(field=field):
                self.assertEqual(getattr(self.profile, field), "")

        self.assertEqual(self.profile.tags, [])
        self.assertEqual(self.profile.languages, [])
        self.assertEqual(self.profile.achievements, [])
        self.assertEqual(self.profile.contact_mode, ContactMode.CLOSED)
        self.assertFalse(self.profile.is_directory_visible)

    def test_avatar_file_disappears_from_storage(self):
        path = self.profile.avatar.name
        self.assertTrue(default_storage.exists(path))

        self.delete_account()

        self.assertFalse(default_storage.exists(path))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)

    def test_sent_contact_requests_lose_their_text(self):
        other = CustomUser.objects.create_user(
            email="boris@example.com",
            password=VALID_PASSWORD,
            first_name="Boris",
            last_name="C",
            is_active=True,
        )
        other_profile = MemberProfile(user=other)
        other_profile.ensure_unique_slug()
        other_profile.save()
        request = ContactRequest.objects.create(
            from_user=self.user, to_profile=other_profile, message="Hallo Boris"
        )

        self.delete_account()

        request.refresh_from_db()
        self.assertEqual(request.message, "")

    def test_refresh_tokens_become_invalid(self):
        refresh = RefreshToken.for_user(self.user)
        self.delete_account()

        response = APIClient().post(
            "/api/v1/accounts/login/refresh/",
            # str(): RefreshToken ist ein Objekt, nicht der Token-String.
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_telegram_cleanup_is_triggered(self):
        self.delete_account()
        self.purge.assert_called_once_with(self.user.pk)

    def test_profile_disappears_from_directory(self):
        other = CustomUser.objects.create_user(
            email="boris@example.com",
            password=VALID_PASSWORD,
            first_name="Boris",
            last_name="C",
            is_active=True,
        )
        slug = self.profile.slug
        self.delete_account()

        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.get(f"/api/v1/profiles/{slug}/").status_code, 404)
        self.assertEqual(client.get("/api/v1/profiles/").data["count"], 0)


class PurgeTelegramPresenceTests(TestCase):
    def setUp(self):
        self.api = mock.patch(
            "apps.bot.services.telegram._api_call", return_value={}
        ).start()
        self.addCleanup(mock.patch.stopall)

        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password=VALID_PASSWORD,
            first_name="Anna",
            last_name="B",
            is_active=False,
        )
        self.invite = TelegramInvite.objects.create(
            user=self.user,
            invite_link="https://t.me/+abc123",
            invite_sent_at=timezone.now(),
            used=True,
            used_at=timezone.now(),
            telegram_user_id=987654,
            profile_message_id=555,
            profile_chat_id="-100123",
            profile_content_hash="abc",
            reminder_count=2,
        )

    def called(self) -> list[str]:
        return [call.args[0] for call in self.api.call_args_list]

    def test_post_is_deleted_and_user_removed(self):
        purge_telegram_presence(self.user.pk)

        methods = self.called()
        self.assertEqual(methods[0], "deleteMessage")
        self.assertIn("banChatMember", methods)
        self.assertIn("revokeChatInviteLink", methods)

    def test_telegram_binding_is_resolved(self):
        purge_telegram_presence(self.user.pk)

        self.invite.refresh_from_db()
        self.assertIsNone(self.invite.telegram_user_id)
        self.assertFalse(self.invite.used)
        self.assertIsNone(self.invite.used_at)
        self.assertIsNone(self.invite.invite_link)
        self.assertIsNone(self.invite.invite_sent_at)
        self.assertIsNone(self.invite.profile_message_id)
        self.assertEqual(self.invite.reminder_count, 0)

    def test_line_remains_for_traceability(self):
        purge_telegram_presence(self.user.pk)
        self.assertTrue(TelegramInvite.objects.filter(user=self.user).exists())

    def test_same_telegram_account_can_re_register(self):
        purge_telegram_presence(self.user.pk)

        self.assertIsNone(find_invite_by_telegram_user_id(987654))

    def test_failed_delete_is_logged(self):

        def only_delete_fails(method, **kwargs):
            # Als Funktion statt als Liste: kick_chat_member macht zwei
            # Aufrufe (banChatMember + unbanChatMember), eine Liste wäre an
            # die Aufrufzahl gebunden.
            if method == "deleteMessage":
                raise TelegramAPIError(method, 400, {"description": "too old"})
            return {}

        self.api.side_effect = only_delete_fails

        with self.assertLogs("apps.bot", "ERROR") as logs:
            purge_telegram_presence(self.user.pk)

        self.assertTrue(any("Löschzusage ist offen" in line for line in logs.output))

    def test_without_invite_line_nothing_happens(self):
        TelegramInvite.objects.filter(user=self.user).delete()
        purge_telegram_presence(self.user.pk)
        self.api.assert_not_called()
