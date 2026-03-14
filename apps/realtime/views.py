import random

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.contrib.auth.models import Group

from apps.orders.models import Order
from apps.accounts.models import CustomUser
from apps.accounts.views import user_is_staff
from apps.core.enums import UserGroup
from .models import ChatRoom, ChatMessage, Notification
from .serializers import (
    ChatRoomSerializer,
    ChatRoomDetailSerializer,
    ChatRoomCreateSerializer,
    ChatMessageSerializer,
    NotificationSerializer,
)


def get_random_operator():
    """Get a random active operator from the Operator group."""
    try:
        operator_group = Group.objects.get(name=UserGroup.OPERATOR.value)
        operators = CustomUser.objects.filter(
            groups=operator_group,
            is_active=True
        )
        if operators.exists():
            return random.choice(list(operators))
    except Group.DoesNotExist:
        pass
    return None


# =============================================================================
# Chat Room Views
# =============================================================================

@extend_schema_view(
    get=extend_schema(
        tags=['Чат'],
        summary='Список моих чатов',
        description='Получить список всех чат-комнат пользователя',
    ),
    post=extend_schema(
        tags=['Чат'],
        summary='Создать чат-комнату',
        description='Создать новую чат-комнату для заказа',
        request=ChatRoomCreateSerializer,
    ),
)
class ChatRoomListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get list of user's chat rooms."""
        user = request.user
        
        if user_is_staff(user):
            # Staff sees all chats where they are receiver
            rooms = ChatRoom.objects.filter(receiver=user, is_active=True)
        else:
            # Customer sees their initiated chats
            rooms = ChatRoom.objects.filter(initiator=user, is_active=True)
        
        rooms = rooms.select_related('initiator', 'receiver', 'order').prefetch_related('messages')
        serializer = ChatRoomSerializer(rooms, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        """Create a new chat room for an order."""
        serializer = ChatRoomCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        order_id = serializer.validated_data['order_id']
        
        # Check order exists
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response({'detail': 'Заказ не найден'}, status=status.HTTP_404_NOT_FOUND)

        
        # Check if chat room already exists
        existing_room = ChatRoom.objects.select_related(
            'initiator', 'receiver', 'order'
        ).prefetch_related('messages__sender').filter(order=order).first()
        
        if existing_room:
            return Response(
                ChatRoomDetailSerializer(existing_room, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        
        # Auto-assign a random operator as receiver
        receiver = get_random_operator()
        
        # Create chat room
        room = ChatRoom.objects.create(
            order=order,
            initiator=request.user,
            receiver=receiver,
        )
        
        # Reload with relations
        room = ChatRoom.objects.select_related(
            'initiator', 'receiver', 'order'
        ).prefetch_related('messages__sender').get(pk=room.pk)
        
        return Response(
            ChatRoomDetailSerializer(room, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    get=extend_schema(
        tags=['Чат'],
        summary='Получить чат-комнату',
        description='Получить детали чат-комнаты с сообщениями',
    ),
    delete=extend_schema(
        tags=['Чат'],
        summary='Закрыть чат-комнату',
        description='Деактивировать чат-комнату',
    ),
)
class ChatRoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Get chat room details with messages."""
        try:
            room = ChatRoom.objects.select_related(
                'initiator', 'receiver', 'order'
            ).prefetch_related(
                'messages__sender'
            ).get(pk=pk)
        except ChatRoom.DoesNotExist:
            return Response({'detail': 'Чат не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if not room.is_participant(request.user) and not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        
        # Mark messages as read
        room.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        
        serializer = ChatRoomDetailSerializer(room, context={'request': request})
        return Response(serializer.data)

    def delete(self, request, pk):
        """Deactivate chat room."""
        try:
            room = ChatRoom.objects.get(pk=pk)
        except ChatRoom.DoesNotExist:
            return Response({'detail': 'Чат не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if not room.is_participant(request.user) and not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        
        room.is_active = False
        room.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=['Чат'],
        summary='Чат по заказу',
        description='Получить чат-комнату для заказа по order_id',
    ),
)
class ChatRoomByOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        """Get chat room for an order."""
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response({'detail': 'Заказ не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if order.user != request.user and not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get chat room
        try:
            room = ChatRoom.objects.select_related(
                'initiator', 'receiver', 'order'
            ).prefetch_related(
                'messages__sender'
            ).get(order=order)
        except ChatRoom.DoesNotExist:
            return Response({'detail': 'Чат для этого заказа не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Mark messages as read
        room.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        
        serializer = ChatRoomDetailSerializer(room, context={'request': request})
        return Response(serializer.data)


# =============================================================================
# Chat Message Views
# =============================================================================

@extend_schema_view(
    get=extend_schema(
        tags=['Чат'],
        summary='Сообщения чата',
        description='Получить все сообщения чат-комнаты. Для отправки используйте WebSocket.',
    ),
)
class ChatMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        """Get all messages in a chat room."""
        try:
            room = ChatRoom.objects.select_related('initiator', 'receiver').get(pk=room_id)
        except ChatRoom.DoesNotExist:
            return Response({'detail': 'Чат не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if not room.is_participant(request.user) and not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        
        messages = room.messages.select_related('sender').order_by('-id')
        
        # Mark as read
        room.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        
        serializer = ChatMessageSerializer(messages, many=True, context={'request': request, 'room': room})
        return Response(serializer.data)


@extend_schema_view(
    patch=extend_schema(
        tags=['Чат'],
        summary='Прочитать сообщения',
        description='Отметить все сообщения в комнате как прочитанные',
    ),
)
class ChatMessageMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, room_id):
        """Mark all messages in room as read."""
        try:
            room = ChatRoom.objects.get(pk=room_id)
        except ChatRoom.DoesNotExist:
            return Response({'detail': 'Чат не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if not room.is_participant(request.user) and not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        
        # Mark messages as read (except own messages)
        count = room.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        
        return Response({'marked_read': count})


# =============================================================================
# Notification Views
# =============================================================================

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Уведомления'], summary='Мои уведомления')
    def get(self, request):
        qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
        return Response(NotificationSerializer(qs, many=True).data)


class UnreadNotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Уведомления'], summary='Непрочитанные уведомления')
    def get(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
        return Response(NotificationSerializer(qs, many=True).data)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Уведомления'], summary='Отметить уведомление прочитанным')
    def patch(self, request, pk):
        try:
            n = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        n.is_read = True
        n.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Уведомления'], summary='Отметить все уведомления прочитанными')
    def patch(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'marked_read': count})
