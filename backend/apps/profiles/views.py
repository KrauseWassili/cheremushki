import mimetypes

from adrf import mixins, viewsets
from adrf.mixins import Response, get_data
from asgiref.sync import sync_to_async
from django.core.files import File
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.throttling import ScopedRateThrottle

from .avatar_files import delete_avatar_files, schedule_avatar_file_deletion
from .file_streaming import streaming_file_response
from .filters import MemberProfileFilter
from .models import ContactRequest, ContactRequestStatus, MemberProfile
from .permissions import IsActiveAuthenticated, IsGroupMember
from .serializers import (
    AvatarUploadSerializer,
    CitySuggestionSerializer,
    ContactRequestCreateSerializer,
    MemberProfileSerializer,
    MyProfileSerializer,
    TagSuggestionSerializer,
    trigger_profile_side_effects,
)
from .services import (
    DEFAULT_SUGGESTION_LIMIT,
    MAX_SUGGESTION_LIMIT,
    resolve_limit,
    suggest_cities,
    suggest_tags,
)
from .tasks import send_contact_request_email

DEFAULT_IMAGE_CONTENT_TYPE = "image/jpeg"
# Felder, die ein Avatar-Upload schreibt. update_fields statt eines vollen
# save(): Ein parallel laufender PATCH auf /me/ soll seine Textfelder nicht
# durch den beim Upload gelesenen Stand überschrieben bekommen. Umgekehrt
# schreibt der PATCH (MemberProfileSerializer.aupdate) nur seine gesendeten
# Felder und nie avatar/avatar_original.
AVATAR_UPLOAD_FIELDS = (
    "avatar",
    "avatar_original",
    "avatar_position_x",
    "avatar_position_y",
    "avatar_scale",
    "avatar_crop_size",
)

SUGGESTION_QUERY_PARAM = OpenApiParameter(
    name="q",
    description="Suchpräfix. Ohne Angabe kommen die häufigsten Einträge.",
    required=False,
    type=str,
)
SUGGESTION_LIMIT_PARAM = OpenApiParameter(
    name="limit",
    description=(
        f"Maximale Anzahl Treffer. Standard {DEFAULT_SUGGESTION_LIMIT}, "
        f"harte Obergrenze {MAX_SUGGESTION_LIMIT}."
    ),
    required=False,
    type=int,
)


async def aget_or_create_profile(user) -> MemberProfile:
    def _get_or_create() -> MemberProfile:
        try:
            return MemberProfile.objects.select_related("user").get(user=user)
        except MemberProfile.DoesNotExist:
            profile = MemberProfile(user=user)
            profile.ensure_unique_slug()
            profile.save()
            return profile

    return await sync_to_async(_get_or_create)()


class ProfileMeViewSet(viewsets.GenericViewSet):
    """
    Eigenes Community-Profil – analog zu accounts.UserMeViewSet.
    """

    serializer_class = MyProfileSerializer
    permission_classes = [IsActiveAuthenticated]
    queryset = MemberProfile.objects.none()

    def get_throttles(self):
        # Jeder Upload dekodiert bis zu zwei Bilder und schreibt sie neu –
        # teuer genug für ein eigenes Limit pro Mitglied.
        if getattr(self, "action", None) == "upload_avatar":
            self.throttle_scope = "avatar"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=["get", "put", "patch"], url_path="me")
    async def me(self, request):
        profile = await aget_or_create_profile(request.user)
        if request.method == "GET":
            serializer = self.get_serializer(profile)
            return Response(await get_data(serializer))

        partial = request.method == "PATCH"
        serializer = self.get_serializer(profile, data=request.data, partial=partial)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        await serializer.asave()
        return Response(await get_data(serializer))

    @action(
        detail=False,
        methods=["post"],
        url_path="me/avatar",
        parser_classes=[MultiPartParser, FormParser],
    )
    async def upload_avatar(self, request):
        """
        Zuschnitt (und optional Original) hochladen.

        Nur JPEG/PNG/WebP bis MAX_AVATAR_UPLOAD_BYTES; gespeichert wird die
        von strip_image_metadata neu geschriebene Fassung ohne Metadaten
        unter Zufallsnamen. Scheitert die Transaktion, werden die schon
        geschriebenen neuen Dateien wieder gelöscht.
        """
        profile = await aget_or_create_profile(request.user)
        serializer = AvatarUploadSerializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        data = serializer.validated_data

        def _save_avatar():
            # Die neuen Dateien landen schon vor dem Commit im Storage. Rollt
            # die Transaktion zurück, verweist keine Zeile auf sie – ohne
            # Aufräumen blieben sie verwaist unter einer gültigen /media/-URL.
            written: list[str] = []
            try:
                with transaction.atomic():
                    # Unter Zeilensperre neu laden: Zwei parallele Uploads
                    # lasen sonst denselben alten Stand, und die Datei des
                    # ersten bliebe verwaist liegen, weil der zweite sie nie
                    # als "ersetzt" sah. of=("self",): nur das Profil
                    # sperren, nicht den User.
                    locked = (
                        MemberProfile.objects.select_for_update(of=("self",))
                        .select_related("user")
                        .get(pk=profile.pk)
                    )
                    # Ersetzte Dateien nach dem Commit löschen. Ohne das
                    # lägen alte Avatare unter weiterhin gültigen
                    # /media/-URLs herum, obwohl das Mitglied sie
                    # ausgetauscht hat.
                    replaced_files = locked.avatar_file_names()
                    _store_avatar_file(locked.avatar, data["avatar"], written)
                    if data.get("avatar_original") is not None:
                        _store_avatar_file(
                            locked.avatar_original, data["avatar_original"], written
                        )
                    locked.avatar_position_x = data.get(
                        "avatar_position_x", locked.avatar_position_x
                    )
                    locked.avatar_position_y = data.get(
                        "avatar_position_y", locked.avatar_position_y
                    )
                    locked.avatar_scale = data.get("avatar_scale", locked.avatar_scale)
                    locked.avatar_crop_size = data.get(
                        "avatar_crop_size", locked.avatar_crop_size
                    )
                    locked.save(update_fields=AVATAR_UPLOAD_FIELDS)
                    became_ready = locked.refresh_directory_visibility(save=True)
                    schedule_avatar_file_deletion(
                        replaced_files - locked.avatar_file_names()
                    )
            except BaseException:
                # Breit, weil nur aufgeräumt und unverändert weitergeworfen
                # wird – auch ein Abbruch (CancelledError im Thread) soll
                # keine Dateien zurücklassen.
                delete_avatar_files(written)
                raise
            return locked, became_ready

        profile, became_ready = await sync_to_async(_save_avatar)()

        # Der Avatar ist Pflichtfeld: Ein Upload kann das Profil vollständig
        # machen und damit die Einladung auslösen.
        await trigger_profile_side_effects(profile, became_ready)
        # Derselbe Serializer wie in me: Das Frontend liest nach dem Upload
        # directory_ready und missing_fields aus der Antwort und muss die
        # Vollständigkeit nicht selbst nachrechnen.
        out = MyProfileSerializer(profile, context={"request": request})
        return Response(await get_data(out), status=status.HTTP_200_OK)

    @extend_schema(
        responses={
            (200, "image/*"): OpenApiTypes.BINARY,
            404: OpenApiResponse(description="Kein Original hochgeladen."),
        }
    )
    @action(detail=False, methods=["get"], url_path="me/avatar/original")
    async def avatar_original(self, request):
        """
        Unbeschnittenes Original des eigenen Avatars, zum erneuten Zuschneiden.

        Nur über diesen Endpunkt: /media/avatars/originals/ ist gesperrt,
        weil das Original mehr zeigt als der Zuschnitt, den das Mitglied
        für das Verzeichnis gewählt hat. Öffnen und Lesen laufen im
        Threadpool (thread_sensitive=False), die Datei wird blockweise
        gestreamt und nicht vorab in den Speicher gelesen.
        """
        profile = await aget_or_create_profile(request.user)
        if not profile.avatar_original:
            raise NotFound("Исходное фото не загружено.")
        name = profile.avatar_original.name
        try:
            handle, size = await sync_to_async(_open_with_size, thread_sensitive=False)(
                profile.avatar_original.storage, name
            )
        except FileNotFoundError as exc:
            raise NotFound("Исходное фото не загружено.") from exc
        content_type = mimetypes.guess_type(name)[0] or DEFAULT_IMAGE_CONTENT_TYPE
        # Gestreamt aus einem Async-Iterator, siehe apps.profiles.file_streaming.
        response = streaming_file_response(handle, size=size, content_type=content_type)
        # private/no-store: Ein geteilter Cache (Proxy) soll das Bild weder
        # ablegen noch einem anderen Nutzer ausliefern.
        response["Cache-Control"] = "private, no-store"
        return response


def _store_avatar_file(field_file, content, written: list[str]) -> None:
    """
    Schreibt die Datei unter Zufallsnamen und merkt sich den Namen fürs
    Aufräumen, falls die Transaktion danach scheitert.
    """
    field_file.save(content.name, content, save=False)
    written.append(field_file.name)


def _open_with_size(storage, name: str) -> tuple[File, int]:
    handle = storage.open(name, "rb")
    return handle, handle.size


class MemberProfileViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Mitgliederverzeichnis und öffentliche Profil-Detailseite.
    """

    serializer_class = MemberProfileSerializer
    # Liste, Detail, Städte und Kontaktanfrage nur für Gruppenmitglieder
    # (E2E F4). Die Kontaktanfrage gehört dazu: Ihr Ziel findet man nur über
    # das Verzeichnis, und sie löst eine Mail an ein Mitglied aus – ohne
    # Gate könnte jeder frisch Registrierte Mitglieder anschreiben, deren
    # Slug er kennt.
    permission_classes = [IsActiveAuthenticated, IsGroupMember]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = MemberProfileFilter
    search_fields = [
        "headline",
        "city",
        "bio",
        "profession",
        "company",
        "user__first_name",
        "user__last_name",
    ]

    def get_queryset(self):
        # prefetch_related("tags"): Sowohl tags als auch tags_detail lesen
        # die Zuordnungen jedes Profils, ohne Prefetch wären das zwei Queries
        # pro Zeile der Verzeichnisliste.
        return (
            MemberProfile.objects.select_related("user")
            .prefetch_related("tags")
            .filter(
                is_directory_visible=True,
                user__is_active=True,
            )
        )

    def get_throttles(self):
        if getattr(self, "action", None) == "contact_request":
            self.throttle_scope = "contact"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    async def alist(self, request, *args, **kwargs):
        def _list():
            return list(self.filter_queryset(self.get_queryset()))

        profiles = await sync_to_async(_list)()
        page = self.paginate_queryset(profiles)
        serializer = self.get_serializer(page or profiles, many=True)
        data = await get_data(serializer)
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    async def aretrieve(self, request, *args, **kwargs):
        profile = await sync_to_async(self.get_object)()
        serializer = self.get_serializer(profile)
        return Response(await get_data(serializer))

    @extend_schema(
        parameters=[SUGGESTION_QUERY_PARAM, SUGGESTION_LIMIT_PARAM],
        responses=TagSuggestionSerializer(many=True),
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="tags",
        permission_classes=[IsActiveAuthenticated],
    )
    async def tag_suggestions(self, request):
        """
        Autocomplete für das kuratierte Tag-Vokabular.

        Ohne Gruppen-Gate: Der Tag-Picker im eigenen Profilformular braucht
        die Liste, bevor jemand beitreten kann. Sie enthält nur das
        Vokabular und Nutzungszahlen, keine Mitgliederdaten.
        """
        limit = resolve_limit(request.query_params.get("limit"))
        query = request.query_params.get("q", "")
        return Response(await sync_to_async(suggest_tags)(query, limit))

    @extend_schema(
        parameters=[SUGGESTION_QUERY_PARAM, SUGGESTION_LIMIT_PARAM],
        responses=CitySuggestionSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="cities")
    async def city_suggestions(self, request):
        """
        Autocomplete für die im Verzeichnis der Städte.
        """
        limit = resolve_limit(request.query_params.get("limit"))
        query = request.query_params.get("q", "")
        return Response(await sync_to_async(suggest_cities)(query, limit))

    @action(
        detail=True,
        methods=["post"],
        url_path="contact-request",
    )
    async def contact_request(self, request, slug=None):
        profile = await sync_to_async(self.get_object)()
        serializer = ContactRequestCreateSerializer(
            data=request.data,
            context={"request": request, "profile": profile},
        )
        await sync_to_async(serializer.is_valid)(raise_exception=True)

        def _create_contact():
            return ContactRequest.objects.create(
                from_user=request.user,
                to_profile=profile,
                message=serializer.validated_data.get("message", ""),
                status=ContactRequestStatus.PENDING,
            )

        contact = await sync_to_async(_create_contact)()
        await sync_to_async(send_contact_request_email.delay)(contact.pk)
        return Response(
            {"detail": "Запрос на контакт отправлен.", "id": contact.pk},
            status=status.HTTP_201_CREATED,
        )
