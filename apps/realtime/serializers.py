from rest_framework import serializers

from .models import ChatMessage, Notification


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'order', 'sender_id', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'sender_id', 'is_read', 'created_at']


class ChatMessageCreateSerializer(serializers.Serializer):
    message = serializers.CharField()


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'type', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']

