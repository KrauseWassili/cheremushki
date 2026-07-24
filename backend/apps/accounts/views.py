from adrf import mixins, viewsets
from adrf.mixins import Response, get_data
from asgiref.sync import sync_to_async
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.bot.tasks.email import send_telegram_invite_email

from .serializers import RegisterSerializer, UserSerializer


class RegisterViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    async def acreate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        user = await serializer.asave()

        await sync_to_async(send_telegram_invite_email.delay)(user.pk)

        user_data = await get_data(UserSerializer(user))
        return Response(
            {
                "user": user_data,
                "detail": (
                    "Registrierung erfolgreich. Bitte prüfe dein Postfach "
                    "und tritt der Telegram-Gruppe bei, um dein Konto zu aktivieren."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class UserMeViewSet(viewsets.GenericViewSet):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

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
