from asgiref.sync import sync_to_async
from adrf import serializers

from .services.telegram import process_chat_member_update


class TelegramWebhookSerializer(serializers.Serializer):
    chat_member = serializers.DictField(required=False)

    async def acreate(self, validated_data):
        chat_member_update = validated_data.get("chat_member")
        if not chat_member_update:
            return None
        await sync_to_async(process_chat_member_update)(chat_member_update)
        return None