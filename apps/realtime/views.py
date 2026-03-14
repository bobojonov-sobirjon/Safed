from asgiref.sync import sync_to_async
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.orders.models import Order
from .models import ChatMessage, Notification
from .serializers import (
    ChatMessageSerializer,
    ChatMessageCreateSerializer,
    NotificationSerializer,
)
from apps.accounts.views import user_is_staff


@extend_schema_view(
    get=extend_schema(tags=['Чат заказов'], summary='Сообщения заказа'),
    post=extend_schema(tags=['Чат заказов'], summary='Отправить сообщение в чат', request=ChatMessageCreateSerializer),
)
class OrderChatView(APIView):
    permission_classes = [IsAuthenticated]

    async def get(self, request, order_id):
        def _get_list():
            try:
                order = Order.objects.get(pk=order_id)
            except Order.DoesNotExist:
                return None
            if order.user != request.user and not user_is_staff(request.user):
                return 'forbidden'
            qs = ChatMessage.objects.filter(order=order).select_related('sender')
            return ChatMessageSerializer(qs, many=True).data

        result = await sync_to_async(_get_list)()
        if result is None:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if result == 'forbidden':
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        return Response(result)

    async def post(self, request, order_id):
        serializer = ChatMessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        message = serializer.validated_data['message']

        def _create():
            try:
                order = Order.objects.get(pk=order_id)
            except Order.DoesNotExist:
                return None, 'not_found'
            if order.user != request.user and not user_is_staff(request.user):
                return None, 'forbidden'
            obj = ChatMessage.objects.create(order=order, sender=request.user, message=message)
            return ChatMessageSerializer(obj).data, 'ok'

        result, code = await sync_to_async(_create)()
        if code == 'not_found':
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if code == 'forbidden':
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        return Response(result, status=status.HTTP_201_CREATED)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Уведомления'], summary='Мои уведомления')
    async def get(self, request):
        def _list():
            qs = Notification.objects.filter(user=request.user).order_by('-created_at')
            return NotificationSerializer(qs, many=True).data

        data = await sync_to_async(_list)()
        return Response(data)


class UnreadNotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Уведомления'], summary='Непрочитанные уведомления')
    async def get(self, request):
        def _list():
            qs = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
            return NotificationSerializer(qs, many=True).data

        data = await sync_to_async(_list)()
        return Response(data)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Уведомления'], summary='Отметить уведомление прочитанным')
    async def patch(self, request, pk):
        def _mark():
            try:
                n = Notification.objects.get(pk=pk, user=request.user)
            except Notification.DoesNotExist:
                return False
            n.is_read = True
            n.save()
            return True

        ok = await sync_to_async(_mark)()
        if not ok:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

