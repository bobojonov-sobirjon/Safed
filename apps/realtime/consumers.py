import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.orders.models import Order
from .models import ChatMessage, Notification


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.user = self.scope.get('user')
        if not self.user or not getattr(self.user, 'is_authenticated', False):
            await self.close(code=4001)
            return

        async def can_join():
            try:
                order = await sync_to_async(Order.objects.select_related('user').get)(pk=self.order_id)
            except Order.DoesNotExist:
                return False
            # owner or staff (operator/admin/courier)
            from apps.accounts.views import user_is_staff  # reuse helper

            if order.user_id == self.user.id:
                return True
            return await sync_to_async(user_is_staff)(self.user)

        if not await can_join():
            await self.close(code=4003)
            return

        self.room_group_name = f'chat_{self.order_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            return

        message = (data.get('message') or '').strip()
        if not message:
            return

        async def create_message():
            order = await sync_to_async(Order.objects.get)(pk=self.order_id)
            obj = await sync_to_async(ChatMessage.objects.create)(
                order=order,
                sender=self.user,
                message=message,
            )
            return {
                'id': obj.id,
                'order': obj.order_id,
                'sender_id': obj.sender_id,
                'message': obj.message,
                'is_read': obj.is_read,
                'created_at': obj.created_at.isoformat(),
            }

        payload = await create_message()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat.message',
                'data': payload,
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['data']))


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not getattr(self.user, 'is_authenticated', False):
            await self.close(code=4001)
            return

        self.group_name = f'notif_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        async def get_unread():
            qs = Notification.objects.filter(user=self.user, is_read=False).order_by('-created_at')
            return [
                {
                    'id': n.id,
                    'title': n.title,
                    'body': n.body,
                    'type': n.type,
                    'is_read': n.is_read,
                    'created_at': n.created_at.isoformat(),
                }
                for n in qs
            ]

        unread = await sync_to_async(get_unread)()
        await self.send(text_data=json.dumps({'type': 'unread_list', 'items': unread}))

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_message(self, event):
        # event['data'] already prepared dict
        await self.send(text_data=json.dumps({'type': 'notification', **event['data']}))

