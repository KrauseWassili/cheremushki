import subprocess
import sys
from pathlib import Path
from unittest import mock

import requests
from django.core.cache import cache
from django.core.checks import messages as checks_messages
from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.accounts.models import CustomUser
from apps.bot import checks as bot_checks
from apps.bot.exceptions import TelegramAPIError, TelegramTransportError
from apps.bot.models import TelegramInvite
from apps.bot.permissions import SECRET_HEADER, IsTelegramWebhook
from apps.bot.services import telegram as telegram_service
from apps.bot.services.profile_card import build_profile_keyboard, build_profile_caption
from apps.bot.tasks import telegram_user as telegram_user_tasks
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
    def test_direct_with_handle_shows_dm_button(self):
        profile = make_profile(
            contact_mode=ContactMode.DIRECT, telegram_username="durov"
        )
        rows = build_profile_keyboard(profile)["inline_keyboard"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0]["url"], "https://t.me/durov")

    def test_request_mode_does_not_display_a_dm_button(self):
        profile = make_profile(
            contact_mode=ContactMode.REQUEST, telegram_username="durov"
        )
        rows = build_profile_keyboard(profile)["inline_keyboard"]
        self.assertEqual(len(rows), 1)

    def test_invalid_handle_is_logged(self):
        profile = make_profile(
            contact_mode=ContactMode.DIRECT,
            telegram_username="https://evil.example.com/x",
        )
        with self.assertLogs("apps.bot.services.profile_card", "WARNING") as logs:
            rows = build_profile_keyboard(profile)["inline_keyboard"]
        self.assertEqual(len(rows), 1)
        self.assertIn("nicht verwertbar", logs.output[0])


class TelegramAPIErrorTests(SimpleTestCase):
    def test_detects_unchanged_message(self):
        self.assertTrue(
            api_error("Bad Request: message is not modified").is_not_modified
        )

    def test_detects_gone_message(self):
        for description in (
            "Bad Request: message to edit not found",
            "Bad Request: message can't be edited",
        ):
            with self.subTest(description=description):
                self.assertTrue(api_error(description).is_message_gone)

    def test_rate_limit_is_neither_unchanged_nor_lost(self):
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

    def test_transport_error_does_not_contain_the_token(self):
        broken = requests.ConnectionError(
            f"Max retries exceeded with url: /bot{FAKE_TOKEN}/editMessageMedia"
        )
        with mock.patch.object(telegram_service.requests, "post", side_effect=broken):
            with self.assertRaises(TelegramTransportError) as ctx:
                telegram_service._api_call("editMessageMedia")

        self.assertNotIn(FAKE_TOKEN, str(ctx.exception))
        # --- Kein __cause__: dessen Message trägt die URL und landet im Traceback.
        self.assertIsNone(ctx.exception.__cause__)

    def test_formatter_maskiert_token_als_zweites_netz(self):
        from config.logging_filters import mask_secrets

        masked = mask_secrets(f"https://api.telegram.org/bot{FAKE_TOKEN}/getMe")
        self.assertNotIn(FAKE_TOKEN, masked)
        self.assertIn("bot<redacted>", masked)


class PostOrUpdateProfileCardTests(SimpleTestCase):
    """
    Der Kern: Wann darf ein zweiter Post entstehen und wann nicht.
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

    def test_unchanged_content_does_not_call_telegram(self):
        payload = telegram_service.build_profile_card_payload(self.profile)
        self.invite.profile_content_hash = payload.digest

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.api.assert_not_called()
        self.assertIsNotNone(self.invite.profile_synced_at)

    def test_message_is_not_modified_is_considered_a_success(self):
        self.api.side_effect = api_error("Bad Request: message is not modified")

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])
        self.assertNotEqual(self.invite.profile_content_hash, "veraltet")

    def test_lost_message_is_posted_again(self):
        self.api.side_effect = [
            api_error("Bad Request: message to edit not found"),
            {"message_id": 999, "chat": {"id": -100123}, "photo": []},
        ]

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia", "sendPhoto"])
        self.assertEqual(self.invite.profile_message_id, 999)

    def test_rate_limit_does_not_create_a_second_post(self):
        self.api.side_effect = api_error(
            "Too Many Requests: retry after 12", status=429, retry_after=12
        )

        with self.assertRaises(TelegramAPIError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_server_error_does_not_create_a_second_post(self):
        self.api.side_effect = api_error("Internal Server Error", status=500)

        with self.assertRaises(TelegramAPIError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_transport_error_does_not_create_a_second_post(self):
        self.api.side_effect = TelegramTransportError("Telegram: ConnectTimeout")

        with self.assertRaises(TelegramTransportError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_db_error_after_successful_edit_does_not_create_a_second_post(self):
        self.api.return_value = {"photo": [{"file_id": "abc"}]}
        self.save.side_effect = DatabaseError("connection lost")

        with self.assertRaises(DatabaseError):
            telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])

    def test_without_an_existing_post_is_sent(self):
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

    def test_true_as_result_does_not_terminate_and_does_not_repost(self):
        """
        editMessageMedia kann True statt einer Message liefern.
        """
        self.api.return_value = True

        telegram_service.post_or_update_profile_card(self.profile, self.invite)

        self.assertEqual(self.called_methods(), ["editMessageMedia"])


class IsTelegramWebhookTests(SimpleTestCase):
    """
    Der Webhook ist die einzige Stelle, an der ein Fremder ohne Konto
    Zustand verändern könnte. Jede Abweichung muss abgelehnt werden.
    """

    def request_with(self, header_value: str | None):
        factory = APIRequestFactory()
        headers = {} if header_value is None else {SECRET_HEADER: header_value}
        return factory.post("/api/v1/bot/telegram/webhook/", {}, headers=headers)

    def allows(self, header_value: str | None) -> bool:
        return IsTelegramWebhook().has_permission(self.request_with(header_value), None)

    @override_settings(TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="s3cret")
    def test_correct_secret_is_allowed(self):
        self.assertTrue(self.allows("s3cret"))

    @override_settings(TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="s3cret")
    def test_incorrect_secret_is_rejected(self):
        self.assertFalse(self.allows("anderes"))

    @override_settings(TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="s3cret")
    def test_missing_header_is_rejected(self):
        self.assertFalse(self.allows(None))

    @override_settings(TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="")
    def test_empty_secret_does_not_open_the_endpoint(self):
        self.assertFalse(self.allows(""))
        self.assertFalse(self.allows(None))
        self.assertFalse(self.allows("irgendwas"))

    @override_settings(TELEGRAM_UPDATE_MODE="polling", TELEGRAM_WEBHOOK_SECRET="s3cret")
    def test_in_polling_mode_also_with_secret_is_rejected(self):
        """
        Ein vergessener setWebhook darf nicht dazu führen, dass Updates
        parallel zum Poller ein zweites Mal verarbeitet werden.
        """
        self.assertFalse(self.allows("s3cret"))


@override_settings(
    TELEGRAM_UPDATE_MODE="polling",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "poller-tests",
        }
    },
)
class PollTelegramUpdatesTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.get_updates = mock.patch.object(
            telegram_user_tasks, "get_updates", return_value=[]
        ).start()
        self.process = mock.patch.object(
            telegram_user_tasks, "process_telegram_update"
        ).start()
        self.addCleanup(mock.patch.stopall)

    def offset(self):
        return cache.get(telegram_user_tasks.OFFSET_CACHE_KEY)

    @override_settings(TELEGRAM_UPDATE_MODE="webhook")
    def test_in_webhook_mode_telegram_is_not_queried(self):
        """Sonst 8.640 Calls pro Tag, die alle mit 409 scheitern."""
        telegram_user_tasks.poll_telegram_updates_task()
        self.get_updates.assert_not_called()

    def test_updates_are_processed_and_the_offset_is_set(self):
        self.get_updates.return_value = [{"update_id": 7}, {"update_id": 8}]
        telegram_user_tasks.poll_telegram_updates_task()
        self.assertEqual(self.process.call_count, 2)
        self.assertEqual(self.offset(), 9)

    def test_api_error_does_not_propagate(self):
        """
        Ein 409 oder Netzwerkfehler darf keinen unbehandelten Task-Fehler
        alle zehn Sekunden erzeugen.
        """
        self.get_updates.side_effect = api_error("Conflict", status=409)
        with self.assertLogs("apps.bot.tasks.telegram_user", "WARNING"):
            telegram_user_tasks.poll_telegram_updates_task()
        self.process.assert_not_called()

    def test_transport_error_does_not_propagate(self):
        self.get_updates.side_effect = TelegramTransportError("ConnectTimeout")
        with self.assertLogs("apps.bot.tasks.telegram_user", "WARNING"):
            telegram_user_tasks.poll_telegram_updates_task()

    def test_unprocessable_update_does_not_pause_the_queue(self):
        """
        Der Offset wandert trotz Fehler weiter, sonst liefert Telegram
        dasselbe Update endlos erneut.
        """
        self.get_updates.return_value = [{"update_id": 3}, {"update_id": 4}]
        self.process.side_effect = [ValueError("kaputt"), None]

        with self.assertLogs("apps.bot.tasks.telegram_user", "ERROR") as logs:
            telegram_user_tasks.poll_telegram_updates_task()

        self.assertIn("nicht verarbeitbar", logs.output[0])
        self.assertEqual(self.process.call_count, 2)
        self.assertEqual(self.offset(), 5)

    def test_lock_prevents_overlapping_runs(self):
        cache.add(
            telegram_user_tasks.POLL_LOCK_KEY,
            "1",
            telegram_user_tasks.POLL_LOCK_TTL_SECONDS,
        )
        telegram_user_tasks.poll_telegram_updates_task()
        self.get_updates.assert_not_called()

    def test_lock_is_released_even_on_error(self):
        """
        Ein hängender Lock würde den Poller bis zum TTL-Ablauf stilllegen.
        """
        self.get_updates.side_effect = RuntimeError("unerwartet")
        with self.assertRaises(RuntimeError):
            telegram_user_tasks.poll_telegram_updates_task()
        self.assertIsNone(cache.get(telegram_user_tasks.POLL_LOCK_KEY))


def check_ids(messages) -> list[str]:
    return [message.id for message in messages]


class TelegramCredentialCheckTests(SimpleTestCase):
    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
    def test_beide_fehlend_ergibt_zwei_befunde(self):
        self.assertEqual(
            check_ids(bot_checks.check_telegram_credentials(None)),
            ["bot.W001", "bot.W002"],
        )

    @override_settings(TELEGRAM_BOT_TOKEN=FAKE_TOKEN, TELEGRAM_CHAT_ID="")
    def test_chat_id_missing(self):
        self.assertEqual(
            check_ids(bot_checks.check_telegram_credentials(None)), ["bot.W002"]
        )

    @override_settings(TELEGRAM_BOT_TOKEN=FAKE_TOKEN, TELEGRAM_CHAT_ID="-100123")
    def test_is_fully_configured(self):
        self.assertEqual(bot_checks.check_telegram_credentials(None), [])


class WebhookSecretCheckTests(SimpleTestCase):
    @override_settings(
        TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="", DEBUG=False
    )
    def test_an_empty_secret_in_production_is_an_error(self):
        """
        Als Error. Ohne Secret lehnt IsTelegramWebhook jede Anfrage ab.
        Der Webhook ist funktionslos.
        """
        messages = bot_checks.check_webhook_secret(None)
        self.assertEqual(check_ids(messages), ["bot.E001"])
        self.assertEqual(messages[0].level, checks_messages.ERROR)

    @override_settings(
        TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="", DEBUG=True
    )
    def test_an_empty_secret_locally_is_only_a_warning(self):
        messages = bot_checks.check_webhook_secret(None)
        self.assertEqual(check_ids(messages), ["bot.W003"])
        self.assertEqual(messages[0].level, checks_messages.WARNING)

    @override_settings(
        TELEGRAM_UPDATE_MODE="polling", TELEGRAM_WEBHOOK_SECRET="", DEBUG=False
    )
    def test_in_polling_mode_the_secret_is_irrelevant(self):
        self.assertEqual(bot_checks.check_webhook_secret(None), [])

    @override_settings(
        TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="s3cret", DEBUG=False
    )
    def test_a_set_secret_is_still_functional(self):
        self.assertEqual(bot_checks.check_webhook_secret(None), [])


class UpdateModeCheckTests(SimpleTestCase):
    @override_settings(
        TELEGRAM_UPDATE_MODE="webhook", FRONTEND_URL="http://localhost:3000"
    )
    def test_webhook_without_https_is_reported(self):
        """
        Sonst verarbeitet niemand Updates: Der Poller steht im
        Webhook-Modus still, und Telegram nimmt keinen http-Webhook an.
        """
        self.assertEqual(
            check_ids(bot_checks.check_update_mode_matches_configuration(None)),
            ["bot.W004"],
        )

    @override_settings(
        TELEGRAM_UPDATE_MODE="webhook", FRONTEND_URL="https://cheremushki.example"
    )
    def test_webhook_with_https_is_functional(self):
        self.assertEqual(bot_checks.check_update_mode_matches_configuration(None), [])

    @override_settings(
        TELEGRAM_UPDATE_MODE="polling", FRONTEND_URL="http://localhost:3000"
    )
    def test_polling_with_localhost_is_the_normal_case(self):
        self.assertEqual(bot_checks.check_update_mode_matches_configuration(None), [])


class CeleryTaskDiscoveryTests(SimpleTestCase):
    def test_worker_finds_all_tasks(self):
        code = (
            "import os, django;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings');"
            "django.setup();"
            "from config.celery import app;"
            "app.loader.import_default_modules();"
            "print(len([t for t in app.tasks if t.startswith('apps.')]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Der Celery-Worker könnte seine Tasks nicht laden und würde nicht "
            f"starten:\n{result.stderr[-2000:]}",
        )
        self.assertGreater(
            int(result.stdout.strip().splitlines()[-1]),
            0,
            "Celery hat keine Projekt-Tasks gefunden.",
        )


class ProfileCaptionContactTests(SimpleTestCase):
    def test_direct_shows_handle_in_caption_and_button(self):
        profile = make_profile(contact_mode=ContactMode.DIRECT, telegram_username="durov")
        caption = build_profile_caption(profile)
        self.assertIn("@durov", caption)
        self.assertIn("https://t.me/durov", caption)
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 2)

    def test_request_hides_handle_even_if_username_is_set(self):
        profile = make_profile(contact_mode=ContactMode.REQUEST, telegram_username="durov")
        caption = build_profile_caption(profile)
        self.assertNotIn("durov", caption)
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 1)

    def test_direct_without_username_has_no_contact(self):
        profile = make_profile(contact_mode=ContactMode.DIRECT, telegram_username="")
        self.assertNotIn("Telegram", build_profile_caption(profile))
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 1)