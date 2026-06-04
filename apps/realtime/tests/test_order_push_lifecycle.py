"""
Buyurtma yaratishdan tugashgacha: har bosqichda to‘g‘ri notification turi va FCM chaqiruvi.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TransactionTestCase

from apps.accounts.models import CustomUser, UserDevice
from apps.core.enums import OrderStatus, PaymentType, UserGroup
from apps.orders.models import Order, OrderCourier
from apps.realtime.models import Notification
from apps.realtime.services.order_notifications import (
    notify_courier_assigned,
    notify_customer_cash_confirmed,
    notify_customer_delivered,
    notify_operators_new_order,
    on_courier_assigned,
    on_order_created,
    on_status_changed,
)


class OrderPushLifecycleTests(TransactionTestCase):
    """Yaratish → confirmed → picking → courier → shipped → delivered → completed."""

    def setUp(self):
        for name in (
            UserGroup.OPERATOR.value,
            UserGroup.COURIER.value,
        ):
            Group.objects.get_or_create(name=name)

        self.operator = CustomUser.objects.create_user(phone='998901111111', password='x')
        self.operator.groups.add(Group.objects.get(name=UserGroup.OPERATOR.value))
        UserDevice.objects.create(
            user=self.operator,
            device_token='op-fcm-' + 'a' * 120,
            device_type='android',
        )

        self.courier = CustomUser.objects.create_user(phone='998902222222', password='x')
        self.courier.groups.add(Group.objects.get(name=UserGroup.COURIER.value))
        UserDevice.objects.create(
            user=self.courier,
            device_token='cr-fcm-' + 'b' * 120,
            device_type='android',
        )

        self.customer = CustomUser.objects.create_user(phone='998903333333', password='x')
        UserDevice.objects.create(
            user=self.customer,
            device_token='cu-fcm-' + 'c' * 120,
            device_type='android',
        )

        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.CREATED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('25000'),
        )

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_full_cash_lifecycle_fcm_calls(self, _ws, mock_fcm):
        order_id = self.order.pk
        courier_id = self.courier.pk

        on_order_created(order_id)
        self.assertTrue(
            Notification.objects.filter(user=self.operator, type='staff_new_order').exists(),
        )

        for new_status, old_status in (
            (OrderStatus.CONFIRMED.value, OrderStatus.CREATED.value),
            (OrderStatus.PICKING.value, OrderStatus.CONFIRMED.value),
        ):
            on_status_changed(order_id, new_status, old_status)

        OrderCourier.objects.create(order=self.order, courier=self.courier)
        on_courier_assigned(order_id, courier_id)
        self.assertTrue(
            Notification.objects.filter(user=self.courier, type='courier_assigned').exists(),
        )
        self.assertTrue(
            Notification.objects.filter(user=self.customer, type='order_courier_assigned').exists(),
        )

        on_status_changed(order_id, OrderStatus.SHIPPED.value, OrderStatus.PICKING.value)
        on_status_changed(order_id, OrderStatus.DELIVERED.value, OrderStatus.SHIPPED.value)
        self.assertTrue(
            Notification.objects.filter(user=self.customer, type='order_delivered').exists(),
        )

        on_status_changed(order_id, OrderStatus.COMPLETED.value, OrderStatus.DELIVERED.value)
        notify_customer_cash_confirmed(order_id)

        customer_types = set(
            Notification.objects.filter(user=self.customer).values_list('type', flat=True),
        )
        self.assertIn('order_status', customer_types)
        self.assertIn('order_delivered', customer_types)
        self.assertIn('order_cash_confirmed', customer_types)

        self.assertGreaterEqual(mock_fcm.call_count, 5)

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=0)
    @patch('apps.realtime.services.notify._push_ws')
    def test_no_fcm_when_customer_has_no_device(self, _ws, mock_fcm):
        UserDevice.objects.filter(user=self.customer).delete()
        on_status_changed(self.order.pk, OrderStatus.CONFIRMED.value, OrderStatus.CREATED.value)
        self.assertTrue(
            Notification.objects.filter(user=self.customer, type='order_status').exists(),
        )
        mock_fcm.assert_not_called()

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_courier_without_token_still_gets_db_notification(self, _ws, _fcm):
        UserDevice.objects.filter(user=self.courier).delete()
        notify_courier_assigned(self.order.pk, self.courier.pk)
        self.assertTrue(
            Notification.objects.filter(user=self.courier, type='courier_assigned').exists(),
        )

    @patch('apps.realtime.services.notify.send_fcm_to_tokens', return_value=1)
    @patch('apps.realtime.services.notify._push_ws')
    def test_operator_new_order_without_operator_group_gets_no_staff_push(self, _ws, mock_fcm):
        self.operator.groups.clear()
        notify_operators_new_order(self.order.pk)
        self.assertFalse(
            Notification.objects.filter(type='staff_new_order').exists(),
        )
        mock_fcm.assert_not_called()
