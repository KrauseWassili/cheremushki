from adrf import mixins, viewsets
from asgiref.sync import sync_to_async
from rest_framework import status
from rest_framework.response import Response

from .models import TelegramInvite
from .permissions import IsTelegramWebhook
from .serializers import TelegramWebhookSerializer


class TelegramWebhookViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = TelegramWebhookSerializer
    permission_classes = [IsTelegramWebhook]
    queryset = TelegramInvite.objects.none()  # GenericViewSet requires a `queryset` attribute

    async def acreate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        await serializer.asave()
        # Does Telegram always expect a 200 OK, regardless of the result?
        # Otherwise, Telegram repeats the update multiple times
        return Response(status=status.HTTP_200_OK)