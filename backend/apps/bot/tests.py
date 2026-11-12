import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import requests
from celery.exceptions import Retry
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.checks import messages as checks_messages
from django.core.checks import run_checks
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.accounts.models import CustomUser
from apps.accounts.services.email import ResendError
from apps.bot import checks as bot_checks
from apps.bot.exceptions import TelegramAPIError, TelegramTransportError
from apps.bot.models import TelegramInvite
from apps.bot.permissions import SECRET_HEADER, IsTelegramWebhook
from apps.bot.services import telegram as telegram_service
from apps.bot.services.invites import (
    INVITE_DISPATCH_DEBOUNCE_SECONDS,
    claim_invite_dispatch,
    has_invite_been_sent,
    is_group_member,
    is_invite_pending,
    release_invite_for_resend,
)
from apps.bot.services.profile_card import (
    CAPTION_MAX_LENGTH,
    build_profile_caption,
    build_profile_keyboard,
    build_profile_url,
    generate_placeholder_avatar,
    resolve_avatar_bytes,
)
from apps.bot.tasks import telegram_user as telegram_user_tasks
from apps.bot.tasks.email import send_telegram_invite_email
from apps.bot.tasks.profile_post import send_profile_completion_reminder
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
        self.assertEqual(rows[0][0]["text"], "Открыть профиль в клубе")
        self.assertIn("/members/anna-b", rows[0][0]["url"])
        self.assertEqual(rows[1][0]["url"], "https://t.me/durov")

    def test_request_mode_does_not_display_a_dm_button(self):
        profile = make_profile(
            contact_mode=ContactMode.REQUEST, telegram_username="durov"
        )
        rows = build_profile_keyboard(profile)["inline_keyboard"]
        self.assertEqual(len(rows), 1)

    def test_group_and_closed_do_not_display_a_dm_button(self):
        for mode in (ContactMode.GROUP, ContactMode.CLOSED):
            with self.subTest(contact_mode=mode):
                profile = make_profile(contact_mode=mode, telegram_username="durov")
                rows = build_profile_keyboard(profile)["inline_keyboard"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][0]["text"], "Открыть профиль в клубе")

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


# token_urlsafe(32)-artig, 43 Zeichen, ohne Platzhalter-Teilstrings.
STRONG_WEBHOOK_SECRET = "Xk3pQ9vR2mT7wL5nB8cZ1hJ4fG6dS0aYuEiOoPqWrTy"


class WebhookSecretStrengthCheckTests(SimpleTestCase):
    @staticmethod
    def bot_error_ids(messages) -> list[str]:
        return [m.id for m in messages if m.id == "bot.E002"]

    def test_weak_secret_in_webhook_mode_is_an_error(self):
        for secret in (
            "kurz",
            "x" * 31,
            "TODO_SET_ME",
            "changeme-" + "x" * 40,
            "password",
        ):
            with self.subTest(secret=secret):
                with override_settings(
                    DEBUG=False,
                    TELEGRAM_UPDATE_MODE="webhook",
                    TELEGRAM_WEBHOOK_SECRET=secret,
                ):
                    messages = bot_checks.check_webhook_secret_strength(None)
                self.assertEqual(check_ids(messages), ["bot.E002"])
                self.assertEqual(messages[0].level, checks_messages.ERROR)

    @override_settings(
        DEBUG=False, TELEGRAM_UPDATE_MODE="polling", TELEGRAM_WEBHOOK_SECRET="kurz"
    )
    def test_weak_secret_in_polling_mode_is_irrelevant(self):
        self.assertEqual(bot_checks.check_webhook_secret_strength(None), [])

    @override_settings(
        DEBUG=True, TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="kurz"
    )
    def test_weak_secret_is_silent_with_debug(self):
        self.assertEqual(bot_checks.check_webhook_secret_strength(None), [])

    @override_settings(
        DEBUG=False,
        TELEGRAM_UPDATE_MODE="webhook",
        TELEGRAM_WEBHOOK_SECRET=STRONG_WEBHOOK_SECRET,
    )
    def test_strong_secret_passes(self):
        self.assertEqual(bot_checks.check_webhook_secret_strength(None), [])

    @override_settings(
        DEBUG=False, TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="x" * 32
    )
    def test_secret_of_exactly_min_length_passes(self):
        # MIN_WEBHOOK_SECRET_LENGTH = 32, Grenze inklusive.
        self.assertEqual(bot_checks.check_webhook_secret_strength(None), [])

    @override_settings(
        DEBUG=False, TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET=""
    )
    def test_empty_secret_is_left_to_e001(self):
        self.assertEqual(bot_checks.check_webhook_secret_strength(None), [])

    @override_settings(
        DEBUG=False, TELEGRAM_UPDATE_MODE="webhook", TELEGRAM_WEBHOOK_SECRET="kurz"
    )
    def test_strength_check_runs_only_as_deploy_check(self):
        self.assertEqual(
            self.bot_error_ids(run_checks(include_deployment_checks=False)), []
        )
        self.assertEqual(
            self.bot_error_ids(run_checks(include_deployment_checks=True)),
            ["bot.E002"],
        )


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
        profile = make_profile(
            contact_mode=ContactMode.DIRECT, telegram_username="durov"
        )
        caption = build_profile_caption(profile)
        self.assertIn("@durov", caption)
        self.assertIn("https://t.me/durov", caption)
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 2)

    def test_request_hides_handle_even_if_username_is_set(self):
        profile = make_profile(
            contact_mode=ContactMode.REQUEST, telegram_username="durov"
        )
        caption = build_profile_caption(profile)
        self.assertNotIn("@durov", caption)
        self.assertNotIn("t.me/durov", caption)
        self.assertNotIn("<b>Telegram</b>", caption)
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 1)

    def test_group_and_closed_hide_handle_even_if_username_is_set(self):
        for mode in (ContactMode.GROUP, ContactMode.CLOSED):
            with self.subTest(contact_mode=mode):
                profile = make_profile(contact_mode=mode, telegram_username="durov")
                caption = build_profile_caption(profile)
                self.assertNotIn("@durov", caption)
                self.assertNotIn("t.me/durov", caption)
                self.assertNotIn("<b>Telegram</b>", caption)
                self.assertEqual(
                    len(build_profile_keyboard(profile)["inline_keyboard"]), 1
                )

    def test_direct_with_invalid_handle_has_no_contact(self):
        profile = make_profile(
            contact_mode=ContactMode.DIRECT,
            telegram_username="https://evil.example.com/x",
        )
        caption = build_profile_caption(profile)
        self.assertNotIn("<b>Telegram</b>", caption)
        self.assertNotIn("t.me/", caption)
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 1)

    def test_direct_without_username_has_no_contact(self):
        profile = make_profile(contact_mode=ContactMode.DIRECT, telegram_username="")
        self.assertNotIn("Telegram", build_profile_caption(profile))
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 1)

    def test_long_bio_keeps_telegram_footer_intact(self):
        profile = make_profile(
            contact_mode=ContactMode.DIRECT,
            telegram_username="durov",
            bio="Б" * 2000,
        )
        caption = build_profile_caption(profile)
        self.assertLessEqual(len(caption), CAPTION_MAX_LENGTH)
        self.assertEqual(caption.count("<a "), 1)
        self.assertEqual(caption.count("</a>"), 1)
        self.assertIn("@durov", caption)
        self.assertIn("https://t.me/durov", caption)
        self.assertTrue(caption.endswith("</a>"))
        self.assertEqual(len(build_profile_keyboard(profile)["inline_keyboard"]), 2)


class ProfileCaptionHeadlineTests(SimpleTestCase):

    def italic_line(self, caption: str) -> str:
        start = caption.index("<i>")
        end = caption.index("</i>", start) + len("</i>")
        return caption[start:end]

    def test_headline_only_without_profession_is_the_subtitle(self):
        profile = make_profile(headline="ЗАГОЛОВОК", profession="")
        caption = build_profile_caption(profile)
        self.assertEqual(self.italic_line(caption), "<i>ЗАГОЛОВОК · #berlin</i>")

    def test_profession_does_not_replace_headline_in_subtitle(self):
        profile = make_profile(headline="ЗАГОЛОВОК", profession="ПРОФЕССИЯ")
        caption = build_profile_caption(profile)
        italic = self.italic_line(caption)
        self.assertEqual(italic, "<i>ЗАГОЛОВОК · #berlin</i>")
        self.assertNotIn("ПРОФЕССИЯ", italic)
        self.assertNotIn("ПРОФЕССИЯ", caption)

    def test_empty_headline_falls_back_to_participant_not_profession(self):
        profile = make_profile(headline="", profession="ПРОФЕССИЯ")
        caption = build_profile_caption(profile)
        italic = self.italic_line(caption)
        self.assertEqual(italic, "<i>Участник · #berlin</i>")
        self.assertNotIn("ПРОФЕССИЯ", italic)
        self.assertNotIn("ПРОФЕССИЯ", caption)


class ProfileReminderMailTests(TestCase):
    """
    Der Reminder läuft über Resend. Entscheidend ist der Zähler: Es gibt nur
    zwei Mahnungen pro Mitglied, ein Fehlschlag darf keine davon verbrauchen.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        # Profil bleibt leer – genau das ist der Anlass für die Mahnung.
        MemberProfile.objects.create(user=self.user, slug="anna-b")
        self.invite = TelegramInvite.objects.create(user=self.user)

    def test_successful_reminder_counts_up(self):
        with mock.patch("apps.bot.tasks.profile_post.send_email") as send_email:
            send_profile_completion_reminder(self.user.pk)

        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.kwargs["to"], self.user.email)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.reminder_count, 1)
        self.assertIsNotNone(self.invite.last_reminder_at)

    def test_failed_reminder_does_not_consume_an_attempt(self):
        with mock.patch(
            "apps.bot.tasks.profile_post.send_email",
            side_effect=ResendError("Resend down", retryable=False),
        ):
            with self.assertRaises(ResendError):
                send_profile_completion_reminder(self.user.pk)

        self.invite.refresh_from_db()
        self.assertEqual(self.invite.reminder_count, 0)
        self.assertIsNone(self.invite.last_reminder_at)

    def test_sent_invitation_stops_the_reminder(self):
        self.invite.invite_sent_at = timezone.now()
        self.invite.save(update_fields=["invite_sent_at"])

        with mock.patch("apps.bot.tasks.profile_post.send_email") as send_email:
            send_profile_completion_reminder(self.user.pk)

        send_email.assert_not_called()


class ResolveAvatarBytesTests(TestCase):
    """
    Ein Sync-Task kann das Profil laden, kurz bevor ein neuer Upload die alte
    Datei nach dem Commit löscht. Dann muss der neue Avatar gepostet werden,
    nicht der Platzhalter.
    """

    def setUp(self):
        media_root = tempfile.mkdtemp(prefix="profile-card-tests-")
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        self.old_name = default_storage.save(
            "avatars/alt.jpg", ContentFile(b"alter-avatar")
        )
        self.profile = MemberProfile.objects.create(
            user=self.user, slug="anna-b", avatar=self.old_name
        )

    def test_resolve_avatar_bytes_reads_current_file(self):
        data, name = resolve_avatar_bytes(self.profile)
        self.assertEqual((data, name), (b"alter-avatar", "alt.jpg"))

    def test_resolve_avatar_bytes_follows_replaced_avatar(self):
        stale = MemberProfile.objects.select_related("user").get(pk=self.profile.pk)
        new_name = default_storage.save("avatars/neu.jpg", ContentFile(b"neuer-avatar"))
        MemberProfile.objects.filter(pk=self.profile.pk).update(avatar=new_name)
        default_storage.delete(self.old_name)

        data, name = resolve_avatar_bytes(stale)

        self.assertEqual((data, name), (b"neuer-avatar", "neu.jpg"))

    def test_resolve_avatar_bytes_falls_back_to_placeholder_when_file_is_gone(self):
        # DB zeigt weiter auf die gelöschte Datei → kein Nachladen möglich.
        default_storage.delete(self.old_name)

        data, name = resolve_avatar_bytes(self.profile)

        self.assertEqual(name, "avatar.png")
        self.assertEqual(data, generate_placeholder_avatar(self.profile))

    def test_resolve_avatar_bytes_without_avatar_uses_placeholder(self):
        MemberProfile.objects.filter(pk=self.profile.pk).update(avatar=None)
        self.profile.refresh_from_db()

        data, name = resolve_avatar_bytes(self.profile)

        self.assertEqual(name, "avatar.png")
        self.assertTrue(data.startswith(b"\x89PNG"))


# --- E2E F3: Einladung bei Telegram-Fehlern ------------------------------ #


def link_error(status: int, **params) -> TelegramAPIError:
    """Fehlerantwort auf createChatInviteLink mit dem gegebenen HTTP-Status."""
    payload = {"error_code": status, "description": f"Fehler {status}"}
    if params:
        payload["parameters"] = params
    return TelegramAPIError("createChatInviteLink", status, payload)


class TelegramErrorRetryableTests(SimpleTestCase):
    """
    retryable trennt vorübergehende Fehler (Retry lohnt) von
    Fehlkonfiguration (Retry scheitert genauso, also sofort sichtbar machen).
    """

    def test_retryable_by_status_code(self):
        cases = [
            # (Status, Parameter, erwartet)
            (401, {}, False),  # ungültiges Token
            (400, {}, False),  # Bot nicht Admin / falsche Chat-ID
            (403, {}, False),  # Bot aus der Gruppe entfernt
            (429, {"retry_after": 7}, True),  # Drosselung
            (500, {}, True),
            (502, {}, True),
        ]
        for status, params, expected in cases:
            with self.subTest(status=status):
                self.assertIs(link_error(status, **params).retryable, expected)

    def test_retryable_when_retry_after_set_without_429(self):
        # is_rate_limited zählt auch retry_after allein als Drosselung.
        self.assertIs(link_error(400, retry_after=3).retryable, True)

    def test_retryable_transport_error_is_always_true(self):
        self.assertIs(TelegramTransportError("Timeout").retryable, True)


INVITE_COMPLETE_PROFILE = {
    "city": "Berlin",
    "headline": "Designerin",
    "bio": "Kurz über mich",
    "can_help_with": "Design-Reviews",
    "looking_for": "Sparring zu UX",
}


class InviteLinkFailureTests(TestCase):
    """
    Der Task bei Fehlern von createChatInviteLink: Retry nur bei
    vorübergehenden Fehlern, sonst Abbruch mit logger.error. In beiden Fällen
    bleibt die Einladung offen (kein Link, kein invite_sent_at).
    """

    def setUp(self):
        self.create_link = mock.patch(
            "apps.bot.tasks.email.create_single_use_invite_link"
        ).start()
        self.send_email = mock.patch("apps.bot.tasks.email.send_email").start()
        # retry() ersetzt: Celery würde beim Direktaufruf die Exception
        # werfen, geprüft werden soll aber, OB und WIE retry gerufen wird.
        self.retry = mock.patch.object(
            send_telegram_invite_email, "retry", side_effect=Retry()
        ).start()
        self.addCleanup(mock.patch.stopall)

        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )
        MemberProfile.objects.create(
            user=self.user,
            slug="anna-b",
            avatar="avatars/user-1.jpg",
            is_directory_visible=True,
            **INVITE_COMPLETE_PROFILE,
        )
        TelegramInvite.objects.create(user=self.user)

    def assert_invite_still_open(self) -> None:
        invite = TelegramInvite.objects.get(user=self.user)
        self.assertIsNone(invite.invite_link)
        self.assertIsNone(invite.invite_sent_at)
        self.send_email.assert_not_called()

    def test_invite_task_permanent_error_gives_up_without_retry(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.retry.reset_mock()
                error = link_error(status)
                self.create_link.side_effect = error

                with self.assertLogs("apps.bot.tasks.email", "ERROR") as logs:
                    with self.assertRaises(TelegramAPIError) as ctx:
                        send_telegram_invite_email(self.user.pk)

                self.assertIs(ctx.exception, error)
                self.retry.assert_not_called()
                self.assertIn("dauerhafter Telegram-Fehler", logs.output[0])
                self.assert_invite_still_open()

    def test_invite_task_rate_limit_retries_after_telegram_wait_time(self):
        error = link_error(429, retry_after=7)
        self.create_link.side_effect = error

        with self.assertRaises(Retry):
            send_telegram_invite_email(self.user.pk)

        self.retry.assert_called_once_with(exc=error, countdown=7)
        self.assert_invite_still_open()

    def test_invite_task_server_error_retries_with_default_delay(self):
        error = link_error(502)
        self.create_link.side_effect = error

        with self.assertRaises(Retry):
            send_telegram_invite_email(self.user.pk)

        # countdown=None → Celery nimmt default_retry_delay.
        self.retry.assert_called_once_with(exc=error, countdown=None)
        self.assert_invite_still_open()

    def test_invite_task_transport_error_retries_with_default_delay(self):
        error = TelegramTransportError("Timeout")
        self.create_link.side_effect = error

        with self.assertRaises(Retry):
            send_telegram_invite_email(self.user.pk)

        self.retry.assert_called_once_with(exc=error, countdown=None)
        self.assert_invite_still_open()


class InviteStateServiceTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="anna@example.com",
            password="Str0ng!Passwort",
            first_name="Anna",
            last_name="B",
            is_active=True,
        )

    def make_invite(self, **fields) -> TelegramInvite:
        return TelegramInvite.objects.create(user=self.user, **fields)

    # --- is_invite_pending -------------------------------------------------

    def test_is_invite_pending_without_invite_row(self):
        self.assertTrue(is_invite_pending(self.user.pk))

    def test_is_invite_pending_with_empty_row(self):
        self.make_invite()
        self.assertTrue(is_invite_pending(self.user.pk))

    def test_is_invite_pending_with_link_but_unsent_mail(self):
        # Mailversand gescheitert: Link steht, Einladung ist trotzdem offen.
        self.make_invite(invite_link="https://t.me/+abc123")
        self.assertTrue(is_invite_pending(self.user.pk))

    def test_is_invite_pending_false_after_sent_mail(self):
        self.make_invite(invite_sent_at=timezone.now())
        self.assertFalse(is_invite_pending(self.user.pk))

    def test_is_invite_pending_false_after_joining(self):
        # Beitritt ohne erfasste Mail (z. B. sync_telegram_profile --mark-joined).
        self.make_invite(used=True)
        self.assertFalse(is_invite_pending(self.user.pk))

    # --- release_invite_for_resend ----------------------------------------

    def test_release_invite_for_resend_clears_sent_at_and_keeps_link(self):
        self.make_invite(
            invite_link="https://t.me/+abc123", invite_sent_at=timezone.now()
        )

        self.assertTrue(release_invite_for_resend(self.user.pk))

        invite = TelegramInvite.objects.get(user=self.user)
        self.assertIsNone(invite.invite_sent_at)
        self.assertEqual(invite.invite_link, "https://t.me/+abc123")
        self.assertTrue(is_invite_pending(self.user.pk))

    def test_release_invite_for_resend_refuses_joined_member(self):
        sent_at = timezone.now()
        self.make_invite(
            invite_link="https://t.me/+abc123", invite_sent_at=sent_at, used=True
        )

        self.assertFalse(release_invite_for_resend(self.user.pk))

        invite = TelegramInvite.objects.get(user=self.user)
        self.assertEqual(invite.invite_sent_at, sent_at)
        self.assertEqual(invite.invite_link, "https://t.me/+abc123")

    def test_release_invite_for_resend_without_invite_row(self):
        # Nichts zurückzusetzen, aber auch nichts im Weg: Der Task legt die
        # Zeile selbst an.
        self.assertTrue(release_invite_for_resend(self.user.pk))
        self.assertFalse(TelegramInvite.objects.filter(user=self.user).exists())

    # --- is_group_member (E2E F4) -----------------------------------------

    def test_is_group_member_without_invite_row(self):
        self.assertFalse(is_group_member(self.user.pk))

    def test_is_group_member_with_unused_invite(self):
        self.make_invite(invite_sent_at=timezone.now())
        self.assertFalse(is_group_member(self.user.pk))

    def test_is_group_member_with_used_invite(self):
        self.make_invite(used=True)
        self.assertTrue(is_group_member(self.user.pk))

    # --- has_invite_been_sent ----------------------------------------------

    def test_has_invite_been_sent_without_invite_row(self):
        self.assertFalse(has_invite_been_sent(self.user.pk))

    def test_has_invite_been_sent_with_unsent_row(self):
        # Link schon erzeugt, Mail aber nicht raus: gilt nicht als versandt.
        self.make_invite(invite_link="https://t.me/+abc123", invite_sent_at=None)
        self.assertFalse(has_invite_been_sent(self.user.pk))

    def test_has_invite_been_sent_with_timestamp(self):
        self.make_invite(invite_sent_at=timezone.now())
        self.assertTrue(has_invite_been_sent(self.user.pk))


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "invite-dispatch-tests",
        }
    },
)
class ClaimInviteDispatchTests(SimpleTestCase):
    """Die Dispatch-Sperre arbeitet nur auf dem Cache, ohne DB."""

    USER_ID = 42

    def setUp(self):
        # Wie in den übrigen Cache-Tests: nie den echten Redis leeren.
        cache.clear()

    def test_claim_invite_dispatch_first_call_wins(self):
        self.assertTrue(claim_invite_dispatch(self.USER_ID))

    def test_claim_invite_dispatch_second_call_is_blocked(self):
        claim_invite_dispatch(self.USER_ID)
        self.assertFalse(claim_invite_dispatch(self.USER_ID))

    def test_claim_invite_dispatch_is_per_user(self):
        claim_invite_dispatch(self.USER_ID)
        self.assertTrue(claim_invite_dispatch(self.USER_ID + 1))

    def test_claim_invite_dispatch_force_ignores_existing_lock(self):
        claim_invite_dispatch(self.USER_ID)
        self.assertTrue(claim_invite_dispatch(self.USER_ID, force=True))
        self.assertTrue(claim_invite_dispatch(self.USER_ID, force=True))

    def test_claim_invite_dispatch_force_sets_lock(self):
        # Ohne vorherige Sperre: force legt sie an, ein normaler Aufruf
        # danach (z. B. Speichern durch den Nutzer) geht leer aus.
        self.assertTrue(claim_invite_dispatch(self.USER_ID, force=True))
        self.assertFalse(claim_invite_dispatch(self.USER_ID))

    def test_claim_invite_dispatch_debounce_covers_retry_window(self):
        # Solange der Task samt Retries noch laufen kann, darf kein zweiter
        # Task angestoßen werden. Heute: 4 × (30 s + 15 s) + 3 × 30 s = 270 s.
        # Wer Retries oder Timeouts hochsetzt, muss die Sperre mitziehen.
        task = send_telegram_invite_email
        attempts = task.max_retries + 1
        worst_case = (
            attempts * (telegram_service.API_TIMEOUT_SECONDS + settings.RESEND_TIMEOUT)
            + task.max_retries * task.default_retry_delay
        )
        self.assertGreater(INVITE_DISPATCH_DEBOUNCE_SECONDS, worst_case)


# --- E2E F6: Profil-Link ohne Slug --------------------------------------- #


@override_settings(FRONTEND_URL="https://club.example")
class BuildProfileUrlTests(SimpleTestCase):
    def test_build_profile_url_with_slug(self):
        self.assertEqual(
            build_profile_url(make_profile(slug="anna-b")),
            "https://club.example/members/anna-b",
        )

    def test_build_profile_url_without_slug_points_to_directory(self):
        # make_profile: user_id=42. Weder ein erfundener member-<id>-Slug noch
        # die ID selbst dürfen im Link landen.
        url = build_profile_url(make_profile(slug=""))

        self.assertEqual(url, "https://club.example/members")
        self.assertNotIn("member-", url)
        self.assertNotIn("42", url)
