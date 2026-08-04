from adrf import serializers
from asgiref.sync import sync_to_async
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import CustomUser


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    JWT-Login mit klarer Fehlermeldung für noch nicht aktivierte Konten
    (E-Mail-Aktivierung: is_active=False bis Klick auf Aktivierungslink).
    """

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        password = attrs.get("password")

        if email:
            email = email.lower().strip()
            attrs[self.username_field] = email

        user = (
            CustomUser.objects.filter(email__iexact=email).first() if email else None
        )

        if user and not user.is_active and user.check_password(password):
            raise ValidationError(
                {
                    "detail": (
                        "Аккаунт ещё не активирован. Проверь почту и перейди "
                        "по ссылке активации."
                    )
                }
            )

        return super().validate(attrs)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
        ]
        extra_kwargs = {
            "email": {"validators": []},
        }

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise ValidationError("Diese E-Mail ist bereits registriert.")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise ValidationError(
                {"password_confirm": "Passwörter stimmen nicht überein."}
            )

        try:
            validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise ValidationError({"password": exc.messages}) from exc
        return attrs

    async def acreate(self, validated_data):
        validated_data.setdefault("street", "")
        validated_data.setdefault("zip_code", "")
        validated_data.setdefault("city", "")
        validated_data.setdefault("is_active", False)
        return await sync_to_async(CustomUser.objects.create_user)(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)
    telegram_joined = serializers.SerializerMethodField(read_only=True)
    has_telegram_invite = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "customer_number",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "is_staff",
            "telegram_joined",
            "has_telegram_invite",
        ]
        read_only_fields = [
            "id",
            "customer_number",
            "email",
            "is_active",
            "is_staff",
            "full_name",
            "telegram_joined",
            "has_telegram_invite",
        ]

    async def get_full_name(self, obj) -> str:
        return obj.full_name

    async def get_telegram_joined(self, obj) -> bool:
        def _check() -> bool:
            from apps.bot.models import TelegramInvite

            return TelegramInvite.objects.filter(user_id=obj.pk, used=True).exists()

        return await sync_to_async(_check)()

    async def get_has_telegram_invite(self, obj) -> bool:
        def _check() -> bool:
            from apps.bot.models import TelegramInvite

            return TelegramInvite.objects.filter(
                user_id=obj.pk, invite_link__isnull=False
            ).exclude(invite_link="").exists()

        return await sync_to_async(_check)()


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise ValidationError(
                {"current_password": "Aktuelles Passwort ist falsch."}
            )
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise ValidationError(
                {"new_password_confirm": "Passwörter stimmen nicht überein."}
            )
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": exc.messages}) from exc
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise ValidationError(
                {"new_password_confirm": "Passwörter stimmen nicht überein."}
            )
        return attrs


class AccountDeleteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise ValidationError("Passwort ist falsch.")
        return value


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class AccountActivationSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
