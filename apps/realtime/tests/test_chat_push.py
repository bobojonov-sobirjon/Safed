"""
Chat WS xabari → qabul qiluvchiga FCM push matnlari (kimdan → kimga).
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TransactionTestCase

from apps.accounts.models import CustomUser, UserDevice
from apps.core.enums import OrderStatus, PaymentType, UserGroup
from apps.orders.models import Order
from apps.realtime.models import ChatMessage, ChatRoom, Notification
from apps.realtime.services.chat_notifications import (
    build_chat_push_texts,
    notify_chat_receiver,
)


class ChatPushNotificationTests(TransactionTestCase):
    def setUp(self):
        Group.objects.get_or_create(name=UserGroup.OPERATOR.value)
        Group.objects.get_or_create(name=UserGroup.COURIER.value)

        self.customer = CustomUser.objects.create_user(
            phone='998901010101',
            password='x',
            first_name='Ali',
        )
        self.operator = CustomUser.objects.create_user(phone='998902020202', password='x')
        self.operator.groups.add(Group.objects.get(name=UserGroup.OPERATOR.value))
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

    def test_customer_to_operator_push_copy(self):
        title, body = build_chat_push_texts(
            sender=self.customer,
            receiver=self.operator,
            order_id=self.order.pk,
            message_preview='Qachon yetkazasiz?',
        )
        self.assertEqual(title, 'Сообщение от покупателя')
        self.assertIn('Ali', body)
        self.assertIn(f'№{self.order.pk}', body)
        self.assertIn('Qachon yetkazasiz', body)

    def test_operator_to_customer_push_copy(self):
        title, body = build_chat_push_texts(
            sender=self.operator,
            receiver=self.customer,
            order_id=self.order.pk,
            message_preview='Tez orada yetkazamiz',
        )
        self.assertEqual(title, 'Сообщение от оператора')
        self.assertIn(f'№{self.order.pk}', body)
        self.assertIn('Tez orada', body)

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
            receiver=self.operator,
        )
        mock_ws.assert_not_called()
        notif = Notification.objects.get(user=self.operator, type='chat_message')
        self.assertEqual(notif.title, 'Сообщение от покупателя')
        self.assertIn('Salom', notif.body)
        mock_fcm.assert_called_once()
        self.assertEqual(mock_fcm.call_args.kwargs['title'], notif.title)

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
            sender=self.customer,
            receiver=self.operator,
        )
        self.assertEqual(mock_fcm.call_args.kwargs['data'].get('type'), 'chat_message')
        self.assertEqual(mock_fcm.call_args.kwargs['data'].get('sender_role'), 'customer')

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
            sender=self.customer,
            receiver=self.operator,
        )
        self.assertTrue(
            Notification.objects.filter(user=self.operator, type='chat_message').exists(),
        )
        mock_fcm.assert_not_called()

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_sender_does_not_get_own_chat_push(self, _ws, mock_fcm):
        notify_chat_receiver(
            receiver_id=self.operator.pk,
            room_id=self.room.pk,
            order_id=self.order.pk,
            sender_id=self.customer.pk,
            message_id=1,
            message_preview='Xabar',
            sender=self.customer,
            receiver=self.operator,
        )
        self.assertFalse(
            Notification.objects.filter(user=self.customer, type='chat_message').exists(),
        )
        mock_fcm.assert_called_once()
