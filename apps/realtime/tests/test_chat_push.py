"""
Chat WS xabari → qabul qiluvchiga FCM push (oldingi kod faqat WS + DB edi).
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TransactionTestCase

from apps.accounts.models import CustomUser, UserDevice
from apps.core.enums import OrderStatus, PaymentType
from apps.orders.models import Order
from apps.realtime.models import ChatMessage, ChatRoom, Notification
from apps.realtime.services.chat_notifications import notify_chat_receiver


class ChatPushNotificationTests(TransactionTestCase):
    def setUp(self):
        self.customer = CustomUser.objects.create_user(phone='998901010101', password='x')
        self.operator = CustomUser.objects.create_user(phone='998902020202', password='x')
        UserDevice.objects.create(
            user=self.operator,
            device_token='op-chat-' + 'a' * 120,
            device_type='android',
        )
        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.CREATED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('10000'),
        )
        self.room = ChatRoom.objects.create(
            order=self.order,
            initiator=self.customer,
            receiver=self.operator,
        )

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_chat_message_sends_fcm_to_receiver(self, mock_ws, mock_fcm):
        msg = ChatMessage.objects.create(
            room=self.room,
            sender=self.customer,
            message='Salom, qachon keladi?',
        )
        notify_chat_receiver(
            receiver_id=self.operator.pk,
            room_id=self.room.pk,
            order_id=self.order.pk,
            sender_id=self.customer.pk,
            message_id=msg.pk,
            message_preview=msg.message,
            sender=self.customer,
        )
        mock_ws.assert_not_called()

        notif = Notification.objects.get(user=self.operator, type='chat_message')
        self.assertEqual(notif.data['room_id'], self.room.pk)
        self.assertEqual(notif.data['order_id'], self.order.pk)
        mock_fcm.assert_called_once()
        call_kwargs = mock_fcm.call_args
        self.assertIn('op-chat-', call_kwargs[0][0][0])

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_chat_title_uses_sender_phone(self, _ws, mock_fcm):
        notify_chat_receiver(
            receiver_id=self.operator.pk,
            room_id=self.room.pk,
            order_id=self.order.pk,
            sender_id=self.customer.pk,
            message_id=1,
            message_preview='Salom',
            sender=self.customer,
        )
        notif = Notification.objects.get(user=self.operator, type='chat_message')
        self.assertEqual(notif.title, self.customer.phone)

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_chat_fcm_payload_contains_chat_type(self, _ws, mock_fcm):
        notify_chat_receiver(
            receiver_id=self.operator.pk,
            room_id=self.room.pk,
            order_id=self.order.pk,
            sender_id=self.customer.pk,
            message_id=1,
            message_preview='Test',
        )
        _, kwargs = mock_fcm.call_args
        self.assertEqual(kwargs['data'].get('type'), 'chat_message')

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_chat_skips_fcm_when_receiver_has_no_device(self, _ws, mock_fcm):
        UserDevice.objects.filter(user=self.operator).delete()
        notify_chat_receiver(
            receiver_id=self.operator.pk,
            room_id=self.room.pk,
            order_id=self.order.pk,
            sender_id=self.customer.pk,
            message_id=1,
            message_preview='Test',
        )
        self.assertTrue(
            Notification.objects.filter(user=self.operator, type='chat_message').exists(),
        )
        mock_fcm.assert_not_called()

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_sender_does_not_get_own_chat_push(self, _ws, mock_fcm):
        """Yuboruvchi o‘ziga push olmaydi — faqat receiver."""
        notify_chat_receiver(
            receiver_id=self.operator.pk,
            room_id=self.room.pk,
            order_id=self.order.pk,
            sender_id=self.customer.pk,
            message_id=1,
            message_preview='Xabar',
        )
        self.assertFalse(
            Notification.objects.filter(user=self.customer, type='chat_message').exists(),
        )
        mock_fcm.assert_called_once()
