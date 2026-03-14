from rest_framework import serializers

from .models import ChatRoom, ChatMessage, Notification
from apps.accounts.models import CustomUser


class UserMinSerializer(serializers.ModelSerializer):
    """Minimal user info for chat."""
    full_name = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ['id', 'phone', 'groups', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip() or obj.phone
    
    def get_groups(self, obj):
        return list(obj.groups.values_list('name', flat=True))


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages."""
    sender = UserMinSerializer(read_only=True)
    sender_type = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'room', 'sender', 'sender_type', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'room', 'sender', 'is_read', 'created_at']

    def get_sender_type(self, obj):
        """Determine sender_type relative to request.user for frontend layout.
        
        - 'initiator' = message sent by request.user (show on right side)
        - 'receiver' = message sent by other user (show on left side)
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if obj.sender_id == request.user.id:
                return 'initiator'
            return 'receiver'
        return None

class ChatMessageCreateSerializer(serializers.Serializer):
    """Serializer for creating chat messages."""
    message = serializers.CharField(required=True, min_length=1, max_length=5000)


class ChatRoomSerializer(serializers.ModelSerializer):
    """Serializer for chat rooms."""
    initiator = UserMinSerializer(read_only=True)
    receiver = UserMinSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatRoom
        fields = [
            'id', 'order', 'initiator', 'receiver', 
            'is_active', 'last_message', 'unread_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'id': last_msg.id,
                'message': last_msg.message[:100],
                'sender_id': last_msg.sender_id,
                'created_at': last_msg.created_at,
                'is_read': last_msg.is_read,
            }
        return None
    
    def get_unread_count(self, obj):
        user = self.context.get('request')
        if user and hasattr(user, 'user'):
            user = user.user
            return obj.messages.filter(is_read=False).exclude(sender=user).count()
        return 0


class ChatRoomDetailSerializer(ChatRoomSerializer):
    """Detailed chat room serializer with messages."""
    messages = serializers.SerializerMethodField()
    
    class Meta(ChatRoomSerializer.Meta):
        fields = ChatRoomSerializer.Meta.fields + ['messages']
    
    def get_messages(self, obj):
        """Serialize messages with request context for sender_type."""
        messages = obj.messages.select_related('sender').order_by('-id')
        return ChatMessageSerializer(messages, many=True, context=self.context).data


class ChatRoomCreateSerializer(serializers.Serializer):
    """Serializer for creating chat rooms."""
    order_id = serializers.IntegerField(required=True)


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'type', 'data', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']
