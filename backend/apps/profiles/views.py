from adrf import mixins, viewsets
from adrf.mixins import Response, get_data
from asgiref.sync import sync_to_async
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.throttling import ScopedRateThrottle

from .models import ContactRequest, ContactRequestStatus, MemberProfile
from .permissions import IsActiveAuthenticated
from .serializers import (
    AvatarUploadSerializer,
    ContactRequestCreateSerializer,
    MemberProfileSerializer,
)
from .tasks import send_contact_request_email


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
    """Eigenes Community-Profil – analog zu accounts.UserMeViewSet."""

    serializer_class = MemberProfileSerializer
    permission_classes = [IsActiveAuthenticated]
    queryset = MemberProfile.objects.none()

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
        profile = await aget_or_create_profile(request.user)
        serializer = AvatarUploadSerializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        data = serializer.validated_data

        def _save_avatar():
            profile.avatar = data["avatar"]
            if data.get("avatar_original") is not None:
                profile.avatar_original = data["avatar_original"]
            profile.avatar_position_x = data.get(
                "avatar_position_x", profile.avatar_position_x
            )
            profile.avatar_position_y = data.get(
                "avatar_position_y", profile.avatar_position_y
            )
            profile.avatar_scale = data.get("avatar_scale", profile.avatar_scale)
            profile.avatar_crop_size = data.get(
                "avatar_crop_size", profile.avatar_crop_size
            )
            profile.save()
            profile.refresh_directory_visibility(save=True)
            return profile

        profile = await sync_to_async(_save_avatar)()
        out = MemberProfileSerializer(profile, context={"request": request})
        return Response(await get_data(out), status=status.HTTP_200_OK)


class MemberProfileViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Mitgliederverzeichnis und öffentliche Profil-Detailseite."""

    serializer_class = MemberProfileSerializer
    permission_classes = [IsActiveAuthenticated]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["city"]
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
        return MemberProfile.objects.select_related("user").filter(
            is_directory_visible=True,
            user__is_active=True,
        )

    def get_throttles(self):
        if getattr(self, "action", None) == "contact_request":
            self.throttle_scope = "contact"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    async def alist(self, request, *args, **kwargs):
        def _list():
            queryset = self.filter_queryset(self.get_queryset())
            tags = request.query_params.get("tags")
            if tags:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                for tag in tag_list:
                    queryset = queryset.filter(tags__icontains=tag)
            return list(queryset)

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
            {"detail": "Kontaktanfrage wurde gesendet.", "id": contact.pk},
            status=status.HTTP_201_CREATED,
        )
