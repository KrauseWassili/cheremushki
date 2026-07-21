from adrf import serializers
from asgiref.sync import sync_to_async
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from .models import CustomUser


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
        return await sync_to_async(CustomUser.objects.create_user)(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

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
        ]
        read_only_fields = [
            "id",
            "customer_number",
            "is_active",
            "is_staff",
            "full_name",
        ]

    async def get_full_name(self, obj) -> str:
        return obj.full_name
