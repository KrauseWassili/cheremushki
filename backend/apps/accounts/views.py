from adrf import mixins, viewsets
from adrf.mixins import Response, get_data
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.bot.tasks.account import purge_telegram_presence
from apps.bot.tasks.profile_post import (
    PROFILE_REMINDER_DELAY_SECONDS,
    send_profile_completion_reminder,
)

from .models import CustomUser
from .serializers import (
    AccountActivationSerializer,
    AccountDeleteSerializer,
    CustomTokenObtainPairSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tasks import send_activation_email


class LoginViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    queryset = CustomUser.objects.none()
    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = "login"

    def get_throttles(self):
        # Der Refresh braucht ein eigenes, großzügigeres Limit: Er läuft
        # automatisch aus dem Frontend (Access-Token lebt 15 Minuten) und
        # würde das Login-Limit sonst für echte Anmeldungen verbrauchen.
        if getattr(self, "action", None) == "refresh":
            self.throttle_scope = "token_refresh"
        return [ScopedRateThrottle()]

    async def acreate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="refresh")
    async def refresh(self, request):
        def _validate():
            serializer = TokenRefreshSerializer(
                data=request.data, context={"request": request}
            )
            try:
                serializer.is_valid(raise_exception=True)
            except TokenError as exc:
                raise ValidationError({"detail": str(exc)}) from exc
            return serializer.validated_data

        try:
            data = await sync_to_async(_validate)()
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_401_UNAUTHORIZED)
        return Response(data, status=status.HTTP_200_OK)


class RegisterViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Sign-up-Contract (stabil):
    - 201 + { user, detail }
    - keine JWT-Tokens (Login erst nach E-Mail-Aktivierung / is_active=True)
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    queryset = CustomUser.objects.none()
    throttle_scope = "sign_up"

    def get_throttles(self):
        return [ScopedRateThrottle()]

    async def acreate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        user = await serializer.asave()

        await sync_to_async(send_activation_email.delay)(user.pk)

        user_data = await get_data(UserSerializer(user))
        return Response(
            {
                "user": user_data,
                "detail": (
                    "Регистрация успешна. Проверь почту и перейди по ссылке, "
                    "чтобы активировать аккаунт."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ActivateAccountViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Aktivierung des Kontos über den Link in der E-Mail, anschließend eine Einladung über Telegram.
    """

    serializer_class = AccountActivationSerializer
    permission_classes = [AllowAny]
    queryset = CustomUser.objects.none()
    throttle_scope = "activate"

    def get_throttles(self):
        return [ScopedRateThrottle()]

    async def acreate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        uid_b64 = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]

        def _activate():
            try:
                uid = force_str(urlsafe_base64_decode(uid_b64))
                user = CustomUser.objects.get(pk=uid)
            except (CustomUser.DoesNotExist, ValueError, TypeError, OverflowError):
                return ("invalid_link", None)

            if user.is_active:
                return ("already_active", user)

            if not default_token_generator.check_token(user, token):
                return ("invalid_token", None)

            user.is_active = True
            user.save(update_fields=["is_active"])

            # Invite-Zeile sofort anlegen, auch wenn Celery kurz down ist –
            # aber NICHT versenden. Die Einladung folgt erst, wenn das Profil
            # vollständig ist.
            from apps.bot.models import TelegramInvite

            TelegramInvite.objects.get_or_create(user=user)

            # Erinnerung an das noch leere Profil. Zielgruppe ist jetzt
            # "aktiviert, aber unvollständig"
            send_profile_completion_reminder.apply_async(
                args=[user.pk], countdown=PROFILE_REMINDER_DELAY_SECONDS
            )
            return ("ok", user)

        result, user = await sync_to_async(_activate)()
        if result == "invalid_link":
            return Response(
                {"detail": "Некорректная ссылка активации."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result == "invalid_token":
            return Response(
                {"detail": "Ссылка активации недействительна или устарела."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result == "already_active":
            return Response(
                {
                    "detail": "Аккаунт уже активирован. Можно войти.",
                    "already_active": True,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "detail": (
                    "Аккаунт активирован. Войди и заполни профиль — "
                    "после этого придёт приглашение в Telegram-группу."
                ),
                "already_active": False,
            },
            status=status.HTTP_200_OK,
        )


class UserMeViewSet(viewsets.GenericViewSet):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)
    queryset = CustomUser.objects.none()

    # Absichtlich ohne throttle_scope: Das Frontend ruft /user/me/ bei jedem
    # Seitenaufruf und nach jedem Token-Refresh. Ein Limit hier würde die
    # Anwendung ausbremsen, und der Endpunkt ist authentifiziert und liest nur
    # die eigenen Daten.

    @action(detail=False, methods=["get", "patch"], url_path="me")
    async def me(self, request):
        if request.method == "PATCH":
            serializer = self.get_serializer(
                request.user, data=request.data, partial=True
            )
            await sync_to_async(serializer.is_valid)(raise_exception=True)
            await serializer.asave()
            user_data = await get_data(serializer)
            return Response(user_data)

        user_data = await get_data(self.get_serializer(request.user))
        return Response(user_data)


class LogoutViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]
    queryset = CustomUser.objects.none()
    throttle_scope = "account"

    def get_throttles(self):
        return [ScopedRateThrottle()]

    async def acreate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)

        def _blacklist():
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()

        try:
            await sync_to_async(_blacklist)()
        except TokenError:
            return Response(
                {"detail": "Ungültiger Refresh-Token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"detail": "Erfolgreich abgemeldet."}, status=status.HTTP_200_OK
        )


class PasswordViewSet(viewsets.GenericViewSet):
    queryset = CustomUser.objects.none()

    def get_permissions(self):
        if self.action == "change":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_throttles(self):
        self.throttle_scope = (
            "password_reset" if self.action in ("reset", "reset_confirm") else "account"
        )
        return [ScopedRateThrottle()]

    def get_serializer_class(self):
        if self.action == "change":
            return PasswordChangeSerializer
        if self.action == "reset":
            return PasswordResetRequestSerializer
        if self.action == "reset_confirm":
            return PasswordResetConfirmSerializer
        return PasswordChangeSerializer

    @action(detail=False, methods=["post"], url_path="change")
    async def change(self, request):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        await sync_to_async(serializer.is_valid)(raise_exception=True)

        def _change_password():
            request.user.set_password(serializer.validated_data["new_password"])
            request.user.save(update_fields=["password"])

        await sync_to_async(_change_password)()
        return Response(
            {"detail": "Passwort wurde geändert."}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"], url_path="reset")
    async def reset(self, request):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        email = serializer.validated_data["email"]

        detail = {
            "detail": (
                "Falls ein Konto mit dieser E-Mail existiert, "
                "wurde ein Reset-Link versendet."
            )
        }

        def _send_reset_mail():
            user = CustomUser.objects.filter(email__iexact=email).first()
            if not (user and user.is_active):
                return
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend_url = getattr(
                settings, "FRONTEND_URL", "http://localhost:3000"
            ).rstrip("/")
            reset_url = f"{frontend_url}/password-reset/confirm?uid={uid}&token={token}"
            html_message = render_to_string(
                "emails/password_reset.html",
                {"user": user, "reset_url": reset_url},
            )
            send_mail(
                subject="Passwort zurücksetzen",
                message=f"Passwort zurücksetzen: {reset_url}",
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )

        await sync_to_async(_send_reset_mail)()
        return Response(detail, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="reset/confirm")
    async def reset_confirm(self, request):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)

        def _reset_password():
            try:
                uid = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
                user = CustomUser.objects.get(pk=uid)
            except (CustomUser.DoesNotExist, ValueError, TypeError, OverflowError):
                return ("invalid_link", None)

            if not default_token_generator.check_token(
                user, serializer.validated_data["token"]
            ):
                return ("invalid_token", None)

            new_password = serializer.validated_data["new_password"]
            try:
                validate_password(new_password, user=user)
            except DjangoValidationError as exc:
                return ("validation", exc.messages)

            user.set_password(new_password)
            user.save(update_fields=["password"])
            return ("ok", None)

        result, extra = await sync_to_async(_reset_password)()
        if result == "invalid_link":
            return Response(
                {"detail": "Ungültiger Reset-Link."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result == "invalid_token":
            return Response(
                {"detail": "Reset-Link ist ungültig oder abgelaufen."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result == "validation":
            raise ValidationError({"new_password": extra})

        return Response(
            {"detail": "Passwort wurde zurückgesetzt."}, status=status.HTTP_200_OK
        )


def _blacklist_outstanding_tokens(user) -> None:
    """
    Entzieht allen ausgegebenen Refresh-Tokens die Gültigkeit.
    """
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class AccountDeleteViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = AccountDeleteSerializer
    permission_classes = [IsAuthenticated]
    queryset = CustomUser.objects.none()
    throttle_scope = "account"

    def get_throttles(self):
        return [ScopedRateThrottle()]

    async def acreate(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        await sync_to_async(serializer.is_valid)(raise_exception=True)

        def _soft_delete() -> int:
            """
            Anonymisiert Konto und Profil beim Löschen.
            """
            from apps.profiles.models import ContactRequest, MemberProfile

            user = request.user

            with transaction.atomic():
                user.email = f"deleted-{user.pk}@deleted.local"
                user.first_name = "Gelöscht"
                user.last_name = "Nutzer"
                user.street = ""
                user.street_no = ""
                user.zip_code = ""
                user.city = ""
                user.is_active = False
                user.set_unusable_password()
                user.save(
                    update_fields=[
                        "email",
                        "first_name",
                        "last_name",
                        "street",
                        "street_no",
                        "zip_code",
                        "city",
                        "is_active",
                        "password",
                    ]
                )

                profile = MemberProfile.objects.filter(user=user).first()
                if profile is not None:
                    profile.anonymize()

                # Der Text einer Kontaktanfrage ist Inhalt des Löschenden und
                # liegt beim Empfänger im Postfach – in der Datenbank hat er
                # nach der Löschung nichts mehr zu suchen.
                ContactRequest.objects.filter(from_user=user).update(message="")

                _blacklist_outstanding_tokens(user)

            return user.pk

        user_id = await sync_to_async(_soft_delete)()

        # Telegram außerhalb der Transaktion: Drei Netzwerkaufrufe dürfen die
        # Löschbestätigung nicht verzögern und nicht scheitern lassen. In der
        # Datenbank ist die Löschung an dieser Stelle vollzogen.
        await sync_to_async(purge_telegram_presence.delay)(user_id)

        return Response({"detail": "Аккаунт удалён."}, status=status.HTTP_200_OK)
