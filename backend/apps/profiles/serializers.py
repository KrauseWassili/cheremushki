from asgiref.sync import sync_to_async
from adrf import serializers
from rest_framework.exceptions import ValidationError
from .models import ContactMode, ContactRequest, MemberProfile
from .telegram import InvalidTelegramUsername, parse_telegram_username


class MemberProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.SerializerMethodField()
    joined_at = serializers.DateTimeField(source="user.created_at", read_only=True)
    avatar_url = serializers.SerializerMethodField()
    avatar_original_url = serializers.SerializerMethodField()

    class Meta:
        model = MemberProfile
        fields = [
            "id",
            "slug",
            "full_name",
            "avatar_url",
            "avatar_original_url",
            "avatar_position_x",
            "avatar_position_y",
            "avatar_scale",
            "avatar_crop_size",
            "headline",
            "city",
            "profession",
            "company",
            "position",
            "bio",
            "can_help_with",
            "looking_for",
            "tags",
            "languages",
            "achievements",
            "email",
            "telegram_username",
            "linkedin_url",
            "website_url",
            "contact_mode",
            "telegram_group_url",
            "is_directory_visible",
            "joined_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "avatar_url",
            "avatar_original_url",
            "email",
            "is_directory_visible",
            "joined_at",
        ]

    async def get_email(self, obj: MemberProfile) -> str | None:
        request = self.context.get("request")

        def _email():
            if (
                request
                and request.user.is_authenticated
                and request.user.pk == obj.user_id
            ):
                return obj.user.email
            if obj.contact_mode == ContactMode.DIRECT:
                return obj.user.email
            return None

        return await sync_to_async(_email)()

    async def get_avatar_url(self, obj: MemberProfile) -> str | None:
        def _url():
            if not obj.avatar:
                return None
            request = self.context.get("request")
            url = obj.avatar.url
            return request.build_absolute_uri(url) if request else url

        return await sync_to_async(_url)()

    async def get_avatar_original_url(self, obj: MemberProfile) -> str | None:
        def _url():
            if not obj.avatar_original:
                return None
            request = self.context.get("request")
            url = obj.avatar_original.url
            return request.build_absolute_uri(url) if request else url

        return await sync_to_async(_url)()

    def validate_tags(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("tags muss eine Liste sein.")
        return [str(item).strip() for item in value if str(item).strip()]

    def validate_languages(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("languages muss eine Liste sein.")
        return [str(item).strip() for item in value if str(item).strip()]

    def validate_achievements(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("achievements muss eine Liste sein.")
        return [str(item).strip() for item in value if str(item).strip()]

    def validate_telegram_username(self, value):
        """
        Validiert die Eingabe, damit in der DB genau ein Format steht.
        """
        if not (value or "").strip():
            return ""
        try:
            return parse_telegram_username(value)
        except InvalidTelegramUsername:
            raise ValidationError(
                "Bitte einen gültigen Telegram-Usernamen angeben – "
                "z. B. @durov oder https://t.me/durov."
            )

    def validate_slug(self, value):
        value = (value or "").strip().lower()
        if not value:
            return value
        qs = MemberProfile.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Dieser Slug ist bereits vergeben.")
        return value

    async def aupdate(self, instance, validated_data):
        def _update():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            if not instance.slug:
                instance.ensure_unique_slug()
            instance.save()
            instance.refresh_directory_visibility(save=True)
            return instance

        profile = await sync_to_async(_update)()
        from apps.bot.tasks.profile_post import sync_telegram_profile_post

        await sync_to_async(sync_telegram_profile_post.delay)(profile.user_id)
        return profile


class AvatarUploadSerializer(serializers.Serializer):
    avatar = serializers.ImageField(required=True)
    avatar_original = serializers.ImageField(required=False, allow_null=True)
    avatar_position_x = serializers.FloatField(required=False, default=0.5)
    avatar_position_y = serializers.FloatField(required=False, default=0.5)
    avatar_scale = serializers.FloatField(required=False, default=1.0)
    avatar_crop_size = serializers.FloatField(required=False, default=1.0)


class ContactRequestCreateSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=""
    )

    def validate(self, attrs):
        request = self.context["request"]
        profile: MemberProfile = self.context["profile"]

        if profile.user_id == request.user.pk:
            raise ValidationError("Du kannst dich nicht selbst anfragen.")
        if profile.contact_mode != ContactMode.REQUEST:
            raise ValidationError("Dieses Profil akzeptiert keine Kontaktanfragen.")
        if ContactRequest.objects.filter(
            from_user=request.user, to_profile=profile
        ).exists():
            raise ValidationError("Du hast dieses Mitglied bereits angefragt.")
        return attrs
