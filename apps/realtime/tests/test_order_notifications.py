from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TransactionTestCase

from apps.accounts.models import CustomUser, UserDevice
from apps.core.enums import OrderStatus, PaymentType, UserGroup
from apps.orders.models import Order
from apps.realtime.models import Notification
from apps.realtime.services.order_notifications import (
    notify_staff_new_order,
    notify_staff_order_cancelled,
    on_order_created_cash,
    on_status_changed,
)


class OrderNotificationTests(TransactionTestCase):
    def setUp(self):
        Group.objects.get_or_create(name=UserGroup.OPERATOR.value)
        Group.objects.get_or_create(name=UserGroup.SUPER_ADMIN.value)
        self.operator = CustomUser.objects.create_user(phone='998901010101', password='x')
        self.operator.groups.add(Group.objects.get(name=UserGroup.OPERATOR.value))
        self.customer = CustomUser.objects.create_user(phone='998902020202', password='x')
        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.CREATED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('50000'),
        )
        UserDevice.objects.create(
            user=self.customer,
            device_token='cust-token',
            device_type='android',
        )

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_staff_notified_on_cash_create(self, _ws, _fcm):
        on_order_created_cash(self.order.pk)
        self.assertEqual(
            Notification.objects.filter(type='staff_new_order', user=self.operator).count(),
            1,
        )

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_status_change_customer_russian(self, _ws, _fcm):
        on_status_changed(self.order.pk, OrderStatus.CONFIRMED.value, OrderStatus.CREATED.value)
        n = Notification.objects.get(user=self.customer, type='order_status')
        self.assertIn('подтверждён', n.body.lower())

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=0)
    @patch('apps.realtime.services.notify._push_ws')
    def test_staff_cancelled_notification(self, _ws, _fcm):
        notify_staff_order_cancelled(self.order.pk)
        self.assertEqual(
            Notification.objects.filter(type='staff_order_cancelled', user=self.operator).count(),
            1,
        )

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_status_shipped_notification(self, _ws, _fcm):
        on_status_changed(self.order.pk, OrderStatus.SHIPPED.value, OrderStatus.PICKING.value)
        n = Notification.objects.get(user=self.customer, type='order_status')
        self.assertIn('пути', n.body.lower())

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_status_delivered_push_to_customer(self, _ws, _fcm):
        on_status_changed(self.order.pk, OrderStatus.DELIVERED.value, OrderStatus.SHIPPED.value)
        n = Notification.objects.get(user=self.customer, type='order_delivered')
        self.assertIn('адрес', n.body.lower())
        self.assertEqual(_fcm.call_count, 1)

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=0)
    @patch('apps.realtime.services.notify._push_ws')
    def test_card_create_does_not_notify_staff_hook(self, _ws, _fcm):
        """Card buyurtma yaratilganda staff xabari yo‘q — faqat Click to‘lovdan keyin."""
        Order.objects.create(
            user=self.customer,
            status=OrderStatus.CREATED.value,
            payment_type=PaymentType.CARD.value,
            estimated_total=Decimal('10000'),
        )
        self.assertEqual(Notification.objects.filter(type='staff_new_order').count(), 0)
