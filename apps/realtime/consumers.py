import json
import logging
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ChatRoom, ChatMessage, Notification

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat."""
    
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.user = self.scope.get('user')
        
        logger.info(f"WS Connect: room={self.room_id}, user={self.user}, authenticated={getattr(self.user, 'is_authenticated', False)}")
        
        if not self.user or not getattr(self.user, 'is_authenticated', False):
            logger.warning(f"WS Reject: User not authenticated")
            await self.close(code=4001)
            return

        # Check if user can join this chat room
        can_join = await self._can_join()
        logger.info(f"WS can_join={can_join} for user={self.user.id}")
        
        if not can_join:
            logger.warning(f"WS Reject: User {self.user.id} cannot join room {self.room_id}")
            await self.close(code=4003)
            return

        self.room_group_name = f'chat_room_{self.room_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(f"WS Accepted: user={self.user.id} joined room={self.room_id}")
        
        # Send chat history
        history = await self._get_history()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': history
        }, ensure_ascii=False))

    async def disconnect(self, code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            return

        action = data.get('action', 'message')
        
        if action == 'message':
            await self._handle_message(data)
        elif action == 'read':
            await self._handle_read()
        elif action == 'typing':
            await self._handle_typing(data)

    async def _can_join(self):
        """Check if user can join this chat room."""
        @sync_to_async
        def check():
            try:
                room = ChatRoom.objects.select_related('initiator', 'receiver').get(pk=self.room_id)
            except ChatRoom.DoesNotExist:
                return False
            
            from apps.accounts.views import user_is_staff
            
            if room.is_participant(self.user):
                return True
            return user_is_staff(self.user)
        
        return await check()

    async def _get_history(self):
        """Get chat history."""
        user_id = self.user.id
        
        @sync_to_async
        def get_messages():
            room = ChatRoom.objects.get(pk=self.room_id)
            messages = room.messages.select_related('sender').order_by('-id')[:100]
            return [
                {
                    'id': m.id,
                    'sender': {
                        'id': m.sender.id,
                        'phone': m.sender.phone,
                        'first_name': m.sender.first_name or '',
                        'last_name': m.sender.last_name or '',
                    },
                    'sender_type': 'initiator',
                    'message': m.message,
                    'is_read': m.is_read,
                    'created_at': m.created_at.isoformat(),
                }
                for m in messages
            ]
        
        return await get_messages()

    async def _handle_message(self, data):
        """Handle incoming message."""
        message = (data.get('message') or '').strip()
        if not message:
            return

        @sync_to_async
        def create_message():
            room = ChatRoom.objects.select_related('initiator', 'receiver').get(pk=self.room_id)
            obj = ChatMessage.objects.create(
                room=room,
                sender=self.user,
                message=message,
            )
            room.save()  # Update updated_at
            
            # Determine receiver for notification
            receiver = None
            if room.initiator_id == self.user.id:
                receiver = room.receiver
            elif room.receiver_id == self.user.id:
                receiver = room.initiator
            
            notification_data = None
            if receiver:
                # Create notification for receiver
                notif = Notification.objects.create(
                    user=receiver,
                    title='Новое сообщение',
                    body=message[:100],
                    type='chat_message',
                    data={
                        'room_id': room.id,
                        'order_id': room.order_id,
                        'sender_id': self.user.id,
                        'message_id': obj.id,
                    }
                )
                notification_data = {
                    'receiver_id': receiver.id,
                    'notification': {
                        'id': notif.id,
                        'title': notif.title,
                        'body': notif.body,
                        'type': notif.type,
                        'data': notif.data,
                        'is_read': notif.is_read,
                        'created_at': notif.created_at.isoformat(),
                    }
                }
            
            return {
                'message_payload': {
                    'id': obj.id,
                    'room_id': obj.room_id,
                    'sender': {
                        'id': self.user.id,
                        'phone': self.user.phone,
                        'first_name': self.user.first_name or '',
                        'last_name': self.user.last_name or '',
                    },
                    'sender_type': 'initiator',  # sender always sees their own message as initiator
                    'message': obj.message,
                    'is_read': obj.is_read,
                    'created_at': obj.created_at.isoformat(),
                },
                'notification_data': notification_data,
            }

        result = await create_message()
        
        # Send chat message to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'data': result['message_payload'],
            },
        )
        
        # Send notification to receiver's notification channel
        if result['notification_data']:
            receiver_id = result['notification_data']['receiver_id']
            await self.channel_layer.group_send(
                f'notif_{receiver_id}',
                {
                    'type': 'notification_message',
                    'data': result['notification_data']['notification'],
                },
            )

    async def _handle_read(self):
        """Mark messages as read."""
        @sync_to_async
        def mark_read():
            room = ChatRoom.objects.get(pk=self.room_id)
            count = room.messages.filter(is_read=False).exclude(sender=self.user).update(is_read=True)
            return count
        
        count = await mark_read()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'messages_read',
                'data': {
                    'user_id': self.user.id,
                    'count': count,
                },
            },
        )

    async def _handle_typing(self, data):
        """Handle typing indicator."""
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_typing',
                'data': {
                    'user_id': self.user.id,
                    'is_typing': is_typing,
                },
            },
        )

    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        data = dict(event['data'])
        # Set sender_type based on current user
        sender_id = data.get('sender', {}).get('id')
        if sender_id == self.user.id:
            data['sender_type'] = 'initiator'
        else:
            data['sender_type'] = 'receiver'
        
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': data
        }, ensure_ascii=False))

    async def messages_read(self, event):
        """Send read notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'read',
            'data': event['data']
        }, ensure_ascii=False))

    async def user_typing(self, event):
        """Send typing indicator to WebSocket."""
        # Don't send to the user who is typing
        if event['data']['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'data': event['data']
            }, ensure_ascii=False))


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications."""
    
    async def connect(self):
        self.user = self.scope.get('user')
        
        if not self.user or not getattr(self.user, 'is_authenticated', False):
            await self.close(code=4001)
            return

        self.group_name = f'notif_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send unread notifications
        unread = await self._get_unread()
        await self.send(text_data=json.dumps({
            'type': 'unread_list',
            'items': unread
        }, ensure_ascii=False))

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def _get_unread(self):
        """Get unread notifications."""
        @sync_to_async
        def get_notifications():
            qs = Notification.objects.filter(user=self.user, is_read=False).order_by('-created_at')[:20]
            return [
                {
                    'id': n.id,
                    'title': n.title,
                    'body': n.body,
                    'type': n.type,
                    'data': n.data,
                    'is_read': n.is_read,
                    'created_at': n.created_at.isoformat(),
                }
                for n in qs
            ]
        
        return await get_notifications()

    async def notification_message(self, event):
        """Send notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }, ensure_ascii=False))
