from adrf import serializers
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import ValidationError

from apps.bot.tasks.email import send_telegram_invite_email
from apps.bot.tasks.profile_post import sync_telegram_profile_post

from .avatar_files import (
    MAX_AVATAR_UPLOAD_BYTES,
    InvalidAvatarImage,
    strip_image_metadata,
)
from .hashtags import InvalidHashtag, parse_hashtag
from .models import (
    DIRECTORY_REQUIRED_FIELDS,
    RESERVED_SLUGS,
    ContactMode,
    ContactRequest,
    MemberProfile,
    ProfileTag,
)
from .telegram import InvalidTelegramUsername, parse_telegram_username

# Obergrenze pro Profil. Der Wert ist keine technische Schranke, sondern eine
# fachliche: Zehn Hashtags unter einem Telegram-Post sind noch lesbar, dreißig
# machen die Suche wertlos, weil dann jeder unter jedem Begriff auftaucht.
MAX_PROFILE_TAGS = 10


@extend_schema_field(drf_serializers.ListField(child=drf_serializers.CharField()))
class ProfileTagListField(drf_serializers.Field):
    """
    tags als flache Liste valider Strings in beide Richtungen.

    Das Frontend arbeitet mit string[].
    Die Anzeigenamen liefert das additive tags_detail.

    Erbt von der DRF-Basisklasse, nicht von adrf.serializers.Field: adrf ruft
    ato_representation einer eigenen Field-Klasse direkt im Event-Loop auf,
    während eine reine DRF-Field über sync_to_async läuft. Hier wird die
    Datenbank angefasst, der Thread-Umweg ist hier Pflicht.
    """

    def get_attribute(self, instance: MemberProfile) -> MemberProfile:
        # Der TaggableManager ist kein Attribut, das DRF auflösen könnte, wir
        # nehmen das Profil selbst und fragen in to_representation nach.
        return instance

    def to_representation(self, instance: MemberProfile) -> list[str]:
        # sorted() statt der Einfügereihenfolge: Das Frontend vergleicht die
        # Liste gegen den Formularzustand, dafür muss die Reihenfolge stabil
        # sein und nicht davon abhängen, wann welcher Tag gesetzt wurde.
        return sorted(tag.name for tag in instance.tags.all())

    def to_internal_value(self, data) -> list[ProfileTag]:
        """
        Löst Strings zu ProfileTag-Instanzen der Allowlist auf.

        Gibt Instanzen zurück, keine Strings: TaggableManager.set() legt für
        unbekannte Strings stillschweigend neue Tags an. Nur wenn hier bereits
        Objekte herauskommen, ist die Allowlist tatsächlich dicht.
        """
        if data is None:
            return []
        if not isinstance(data, (list, tuple)):
            raise ValidationError("Теги нужно передать списком.")
        if len(data) > MAX_PROFILE_TAGS:
            raise ValidationError(
                f"Можно выбрать не больше {MAX_PROFILE_TAGS} тегов, "
                f"выбрано {len(data)}."
            )

        canonical_names: list[str] = []
        unparsable: list[str] = []
        for raw_value in data:
            try:
                name = parse_hashtag(str(raw_value))
            except InvalidHashtag:
                unparsable.append(str(raw_value))
                continue
            if name not in canonical_names:
                canonical_names.append(name)

        if unparsable:
            raise ValidationError(
                "Некорректные теги: " + ", ".join(repr(v) for v in unparsable),
                code="invalid_tags",
            )
        if not canonical_names:
            return []

        tags_by_name = {
            tag.name: tag
            for tag in ProfileTag.objects.filter(
                name__in=canonical_names, is_active=True
            )
        }
        unknown = [name for name in canonical_names if name not in tags_by_name]
        if unknown:
            raise ValidationError(
                "Этих тегов нет в словаре или они больше недоступны: "
                + ", ".join(unknown)
                + ". Выбери теги из списка подсказок.",
                code="unknown_tags",
            )

        return [tags_by_name[name] for name in canonical_names]


class TagDetailSchemaSerializer(drf_serializers.Serializer):
    """
    Nur für die OpenAPI Beschreibung von tags_detail wird nicht instanziiert.
    """

    name = drf_serializers.CharField()
    label = drf_serializers.CharField()
    hashtag = drf_serializers.CharField()


@extend_schema_field(TagDetailSchemaSerializer(many=True))
class ProfileTagDetailField(drf_serializers.Field):
    """
    Anzeigenamen und Hashtag-Form zu den gesetzten Tags.
    """

    def get_attribute(self, instance: MemberProfile) -> MemberProfile:
        return instance

    def to_representation(self, instance: MemberProfile) -> list[dict]:
        tags = sorted(instance.tags.all(), key=lambda tag: tag.name)
        return [
            {
                "name": tag.name,
                "label": tag.display_label,
                "hashtag": tag.hashtag,
            }
            for tag in tags
        ]


class MemberProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.SerializerMethodField()
    joined_at = serializers.DateTimeField(source="user.created_at", read_only=True)
    avatar_url = serializers.SerializerMethodField()
    tags = ProfileTagListField(required=False)
    tags_detail = ProfileTagDetailField(read_only=True)

    class Meta:
        model = MemberProfile
        fields = [
            "id",
            "slug",
            "full_name",
            "avatar_url",
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
            "tags_detail",
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
            "email",
            "tags_detail",
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

    def validate_languages(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("Языки нужно передать списком.")
        return [str(item).strip() for item in value if str(item).strip()]

    def validate_achievements(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("Достижения нужно передать списком.")
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
                "Укажи корректный username в Telegram – "
                "например, @durov или https://t.me/durov."
            )

    def validate_slug(self, value):
        value = (value or "").strip().lower()
        if not value:
            return value
        if value in RESERVED_SLUGS:
            # Diese Slugs gehören zu Routen unter /api/v1/profiles/, ein Profil
            # darunter wäre über die API nicht mehr erreichbar.
            raise ValidationError("Этот адрес профиля зарезервирован.")
        qs = MemberProfile.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Этот адрес профиля уже занят.")
        return value

    async def aupdate(self, instance, validated_data):
        tag_objects = validated_data.pop("tags", None)

        def _update():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            if not instance.slug:
                instance.ensure_unique_slug()
            instance.save()
            if tag_objects is not None:
                instance.tags.set(tag_objects)
            became_ready = instance.refresh_directory_visibility(save=True)
            return instance, became_ready

        profile, became_ready = await sync_to_async(_update)()
        await trigger_profile_side_effects(profile, became_ready)
        return profile


class MyProfileSerializer(MemberProfileSerializer):
    """Einsicht eigenes Profil."""

    directory_ready = serializers.SerializerMethodField(read_only=True)
    missing_fields = serializers.SerializerMethodField(read_only=True)
    required_fields = serializers.SerializerMethodField(read_only=True)
    invite_sent = serializers.SerializerMethodField(read_only=True)
    # Nur ein Flag, keine URL: Das Original ist nicht öffentlich ausgeliefert,
    # das Frontend holt es mit Bearer-Token über /user/me/avatar/original/.
    has_avatar_original = serializers.SerializerMethodField(read_only=True)

    class Meta(MemberProfileSerializer.Meta):
        fields = MemberProfileSerializer.Meta.fields + [
            "directory_ready",
            "missing_fields",
            "required_fields",
            "invite_sent",
            "has_avatar_original",
        ]
        read_only_fields = MemberProfileSerializer.Meta.read_only_fields + [
            "directory_ready",
            "missing_fields",
            "required_fields",
            "invite_sent",
            "has_avatar_original",
        ]

    async def get_has_avatar_original(self, obj: MemberProfile) -> bool:
        return bool(obj.avatar_original)

    async def get_directory_ready(self, obj: MemberProfile) -> bool:
        return await sync_to_async(obj.compute_directory_ready)()

    async def get_missing_fields(self, obj: MemberProfile) -> list[str]:
        return await sync_to_async(obj.missing_directory_fields)()

    async def get_invite_sent(self, obj: MemberProfile) -> bool:

        def _check() -> bool:
            from apps.bot.models import TelegramInvite

            return TelegramInvite.objects.filter(
                user_id=obj.user_id, invite_sent_at__isnull=False
            ).exists()

        return await sync_to_async(_check)()

    async def get_required_fields(self, obj: MemberProfile) -> list[str]:
        return list(DIRECTORY_REQUIRED_FIELDS)


async def trigger_profile_side_effects(
    profile: MemberProfile, became_ready: bool
) -> None:
    """
    Löst aus, was nach einer Profiländerung folgt.
    """

    if became_ready:
        await sync_to_async(send_telegram_invite_email.delay)(profile.user_id)

    # Der Profilpost ist ein No-Op, solange kein genutzter Invite existiert
    # der Task prüft das selbst. Er wird trotzdem immer angestoßen, damit
    # Änderungen an einem schon geposteten Profil im Kanal ankommen.
    await sync_to_async(sync_telegram_profile_post.delay)(profile.user_id)


class TagSuggestionSerializer(drf_serializers.Serializer):
    """
    Antwortform von GET /api/v1/profiles/tags/, nur für die OpenAPI Doku.
    """

    name = drf_serializers.CharField(help_text="Valides Token ohne '#'.")
    label = drf_serializers.CharField(help_text="Anzeigename für die Oberfläche.")
    hashtag = drf_serializers.CharField(help_text="Token mit '#' davor.")
    usage_count = drf_serializers.IntegerField(
        help_text="Sichtbare Profile mit diesem Tag."
    )


class CitySuggestionSerializer(drf_serializers.Serializer):
    """
    Antwortform von GET /api/v1/profiles/cities/ – nur für die OpenAPI-Doku.
    """

    name = drf_serializers.CharField(help_text="Stadt, wie sie im Profil steht.")
    hashtag = drf_serializers.CharField(
        help_text="Hashtag-Token ohne '#'; leer, wenn nicht kanonisierbar."
    )
    count = drf_serializers.IntegerField(help_text="Sichtbare Profile in dieser Stadt.")


class AvatarImageField(drf_serializers.ImageField):
    """
    ImageField mit Byte-Obergrenze.

    Die Grenze greift vor super().to_internal_value(): Dort öffnet und prüft
    Pillow die Datei bereits – bei einer übergroßen Datei soll das gar nicht
    erst passieren.
    """

    default_error_messages = {
        "too_large": (
            "Файл слишком большой. Максимум – "
            f"{MAX_AVATAR_UPLOAD_BYTES // (1024 * 1024)} МБ."
        ),
    }

    def to_internal_value(self, data):
        size = getattr(data, "size", None)
        if size is not None and size > MAX_AVATAR_UPLOAD_BYTES:
            self.fail("too_large")
        return super().to_internal_value(data)


class AvatarUploadSerializer(serializers.Serializer):
    avatar = AvatarImageField(required=True)
    avatar_original = AvatarImageField(required=False, allow_null=True)
    avatar_position_x = serializers.FloatField(required=False, default=0.5)
    avatar_position_y = serializers.FloatField(required=False, default=0.5)
    avatar_scale = serializers.FloatField(required=False, default=1.0)
    avatar_crop_size = serializers.FloatField(required=False, default=1.0)

    def validate_avatar(self, value):
        return _sanitize_avatar_image(value)

    def validate_avatar_original(self, value):
        if value is None:
            return None
        return _sanitize_avatar_image(value)


def _sanitize_avatar_image(upload) -> ContentFile:
    """
    Gespeichert wird nur die neu geschriebene Fassung ohne Metadaten – der
    Client kann EXIF mitschicken, egal was das eigene Frontend tut.
    """
    try:
        return strip_image_metadata(upload)
    except InvalidAvatarImage as exc:
        raise ValidationError(exc.user_message) from exc


class ContactRequestCreateSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=""
    )

    def validate(self, attrs):
        request = self.context["request"]
        profile: MemberProfile = self.context["profile"]

        if profile.user_id == request.user.pk:
            raise ValidationError("Нельзя отправить запрос самому себе.")
        if profile.contact_mode != ContactMode.REQUEST:
            raise ValidationError("Этот участник не принимает запросы на контакт.")
        if ContactRequest.objects.filter(
            from_user=request.user, to_profile=profile
        ).exists():
            raise ValidationError("Запрос этому участнику уже отправлен.")
        return attrs
