from asgiref.sync import sync_to_async
from adrf import serializers

from .services.telegram import process_telegram_update


class TelegramWebhookSerializer(serializers.Serializer):
    update_id = serializers.IntegerField(required=False)
    chat_member = serializers.DictField(required=False)
    message = serializers.DictField(required=False)
    channel_post = serializers.DictField(required=False)
    my_chat_member = serializers.DictField(required=False)

    async def acreate(self, validated_data):
        await sync_to_async(process_telegram_update)(validated_data)
        return None
