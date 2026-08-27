from unittest import mock

import requests
from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings

from apps.accounts.models import CustomUser
from apps.bot.exceptions import TelegramAPIError, TelegramTransportError
from apps.bot.models import TelegramInvite
from apps.bot.services import telegram as telegram_service
from apps.bot.services.profile_card import build_profile_keyboard
from apps.profiles.models import ContactMode, MemberProfile

FAKE_TOKEN = "7123456789:AAHmocktokenmocktokenmocktoken12345"
PEOPLE_TOPIC_ID = 3


def make_profile(**kwargs) -> MemberProfile:
    user = CustomUser(id=42, email="a@example.com", first_name="Anna", last_name="B")
    defaults = {
        "user": user,
        "slug": "anna-b",
        "headline": "Designerin",
        "city": "Berlin",
        "contact_mode": ContactMode.REQUEST,
        "telegram_username": "",
    }
    return MemberProfile(**{**defaults, **kwargs})


def api_error(description: str, status: int = 400, **params) -> TelegramAPIError:
    payload = {"error_code": status, "description": description}
    if params:
        payload["parameters"] = params
    return TelegramAPIError("editMessageMedia", status, payload)


class ProfileKeyboardTests(SimpleTestCase):
    def test_direct_mit_handle_zeigt_dm_button(self):
        profile = make_profile(
            contact_mode=ContactMode.DIRECT, telegram_username="durov"
        )
        rows = build_profile_keyboard(profile)["inline_keyboard"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0]["url"], "https://t.me/durov")

    def test_request_modus_zeigt_keinen_dm_button(self):
        """
        Der Post ist öffentlich nur DIRECT gibt den Handle frei.
        """
        profile = make_profile(
            contact_mode=ContactMode.REQUEST, telegram_username="durov"
        )
        rows = build_profile_keyboard(profile)["inline_keyboard"]
        self.assertEqual(len(rows), 1)

    def test_unbrauchbarer_handle_wird_geloggt_statt_verschluckt(self):
        profile = make_profile(
            contact_mode=ContactMode.DIRECT,
            telegram_username="https://evil.example.com/x",
        )
        with self.assertLogs("apps.bot.services.profile_card", "WARNING") as logs:
            rows = build_profile_keyboard(profile)["inline_keyboard"]
        self.assertEqual(len(rows), 1)
        self.assertIn("nicht verwertbar", logs.output[0])


class TelegramAPIErrorTests(SimpleTestCase):
    def test_erkennt_unveraenderte_nachricht(self):
        self.assertTrue(
            api_error("Bad Request: message is not modified").is_not_modified
        )

    def test_erkennt_verlorene_nachricht(self):
        for description in (
            "Bad Request: message to edit not found",
            "Bad Request: message can't be edited",
        ):
            with self.subTest(description=description):
                self.assertTrue(api_error(description).is_message_gone)

    def test_rate_limit_ist_weder_unveraendert_noch_verloren(self):
        exc = api_error("Too Many Requests: retry after 12", status=429, retry_after=12)
        self.assertFalse(exc.is_not_modified)
        self.assertFalse(exc.is_message_gone)
        self.assertTrue(exc.is_rate_limited)
        self.assertEqual(exc.retry_after, 12)


@override_settings(TELEGRAM_BOT_TOKEN=FAKE_TOKEN)
class ApiCallSecretTests(SimpleTestCase):
    """
    Der Bot-Token steckt in jeder URL, er darf in keine Exception geraten.
    """

    def test_transportfehler_enthaelt_den_token_nicht(self):
        broken = requests.ConnectionError(
            f"Max retries exceeded with url: /bot{FAKE_TOKEN}/editMessageMedia"
        )
        with mock.patch.object(telegram_service.requests, "post", side_effect=broken):
            with self.assertRaises(TelegramTransportError) as ctx:
                telegram_service._api_call("editMessageMedia")

        self.assertNotIn(FAKE_TOKEN, str(ctx.exception))
        # Kein __cause__: dessen Message trägt die URL und landet im Traceback.
        self.assertIsNone(ctx.exception.__cause__)

    def test_formatter_maskiert_token_als_zweites_netz(self):
        from config.logging_filters import mask_secrets

        masked = mask_secrets(f"https://api.telegram.org/bot{FAKE_TOKEN}/getMe")
        self.assertNotIn(FAKE_TOKEN, masked)
        self.assertIn("bot<redacted>", masked)


class PostOrUpdateProfileCardTests(SimpleTestCase):
    """
    Der Kern: Wann darf ein zweiter Post entstehen – und wann nicht.
    """

    def setUp(self):
        self.profile = make_profile()
        self.invite = TelegramInvite(
            id=1,
            user_id=42,
            profile_message_id=555,
            profile_chat_id="-100123",
            profile_content_hash="veraltet",
        )

        topic_patch = mock.patch.object(
            telegram_service, "resolve_people_topic_id", return_value=PEOPLE_TOPIC_ID
        )
        save_patch = mock.patch.object(TelegramInvite, "save")
        self.api = mock.patch.object(telegram_service, "_api_call").start()
        topic_patch.start()
        self.save = save_patch.start()
        self.addCleanup(mock.patch.stopall)

    def called_methods(self) -> list[str]:
        return [call.args[0] for call in self.api.call_args_list]

    def test_unveraenderter_inhalt_ruft_telegram_gar_nicht_auf(self):
        payload = telegram_service.build_profile_card_payload(self.profile)
        self.invite.profile_content_hash = payload.digest

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.api.assert_not_called()
        self.assertIsNotNone(self.invite.profile_synced_at)

    def test_message_is_not_modified_gilt_als_erfolg(self):
        self.api.side_effect = api_error("Bad Request: message is not modified")

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])
        self.assertNotEqual(self.invite.profile_content_hash, "veraltet")

    def test_verlorene_nachricht_wird_neu_gepostet(self):
        self.api.side_effect = [
            api_error("Bad Request: message to edit not found"),
            {"message_id": 999, "chat": {"id": -100123}, "photo": []},
        ]

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia", "sendPhoto"])
        self.assertEqual(self.invite.profile_message_id, 999)

    def test_rate_limit_erzeugt_keinen_zweiten_post(self):
        self.api.side_effect = api_error(
            "Too Many Requests: retry after 12", status=429, retry_after=12
        )

        with self.assertRaises(TelegramAPIError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_serverfehler_erzeugt_keinen_zweiten_post(self):
        self.api.side_effect = api_error("Internal Server Error", status=500)

        with self.assertRaises(TelegramAPIError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_transportfehler_erzeugt_keinen_zweiten_post(self):
        self.api.side_effect = TelegramTransportError("Telegram: ConnectTimeout")

        with self.assertRaises(TelegramTransportError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_db_fehler_nach_erfolgreichem_edit_erzeugt_keinen_zweiten_post(self):
        """Der Edit ist durch – ein Fehler beim Speichern darf nicht neu posten."""
        self.api.return_value = {"photo": [{"file_id": "abc"}]}
        self.save.side_effect = DatabaseError("connection lost")

        with self.assertRaises(DatabaseError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_ohne_bestehenden_post_wird_gesendet(self):
        self.invite.profile_message_id = None
        self.api.return_value = {
            "message_id": 777,
            "chat": {"id": -100123},
            "photo": [{"file_id": "xyz"}],
        }

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["sendPhoto"])
        self.assertEqual(self.invite.profile_thread_id, PEOPLE_TOPIC_ID)
        self.assertEqual(self.invite.profile_photo_file_id, "xyz")
        self.assertTrue(self.invite.profile_content_hash)

    def test_true_als_ergebnis_bricht_nicht_und_postet_nicht_neu(self):
        """
        editMessageMedia kann True statt einer Message liefern.
        """
        self.api.return_value = True

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])
