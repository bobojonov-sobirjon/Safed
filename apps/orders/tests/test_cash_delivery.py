from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, PaymentStatus, PaymentType, UserGroup
from apps.orders.models import Order, OrderCourier
from apps.orders.services.cash_delivery import (
    CashDeliveryError,
    assign_cash_qr_token,
    confirm_cash_delivery_by_qr,
    generate_cash_qr_token,
)


class CashDeliveryTests(TestCase):
    def setUp(self):
        self.customer = CustomUser.objects.create_user(phone='998903333333', password='pass12345')
        self.courier = CustomUser.objects.create_user(phone='998904444444', password='pass12345')
        Group.objects.get_or_create(name=UserGroup.COURIER.value)
        self.courier.groups.add(Group.objects.get(name=UserGroup.COURIER.value))

        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.SHIPPED.value,
            payment_type=PaymentType.CASH.value,
            payment_status=PaymentStatus.PENDING.value,
            products_subtotal=Decimal('10000'),
            estimated_total=Decimal('10000'),
        )
        self.token = assign_cash_qr_token(self.order)
        OrderCourier.objects.create(order=self.order, courier=self.courier)

    def _mark_delivered(self):
        self.order.status = OrderStatus.DELIVERED.value
        self.order.delivered_at = timezone.now()
        self.order.save(update_fields=['status', 'delivered_at', 'updated_at'])

    def test_confirm_requires_delivered_first(self):
        with self.assertRaises(CashDeliveryError) as ctx:
            confirm_cash_delivery_by_qr(
                order_id=self.order.pk,
                qr_code=self.token,
                courier_user=self.courier,
            )
        self.assertEqual(ctx.exception.code, 'status')

    def test_confirm_success_sets_completed(self):
        self._mark_delivered()
        order, _ = confirm_cash_delivery_by_qr(
            order_id=self.order.pk,
            qr_code=self.token,
            courier_user=self.courier,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED.value)
        self.assertEqual(order.payment_status, PaymentStatus.PAID.value)
        self.assertIsNone(order.cash_qr_token)
        self.assertIsNotNone(order.qr_confirmed_at)
        self.assertIsNotNone(order.delivered_at)

    def test_confirm_invalid_qr(self):
        self._mark_delivered()
        with self.assertRaises(CashDeliveryError):
            confirm_cash_delivery_by_qr(
                order_id=self.order.pk,
                qr_code='wrong-token',
                courier_user=self.courier,
            )

    def test_confirm_qr_single_use(self):
        self._mark_delivered()
        confirm_cash_delivery_by_qr(
            order_id=self.order.pk,
            qr_code=self.token,
            courier_user=self.courier,
        )
        with self.assertRaises(CashDeliveryError):
            confirm_cash_delivery_by_qr(
                order_id=self.order.pk,
                qr_code=self.token,
                courier_user=self.courier,
            )

    def test_my_orders_shows_qr_only_for_owner_pending_cash(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        resp = client.get('/api/v1/orders/my/')
        self.assertEqual(resp.status_code, 200)
        row = next(x for x in resp.data if x['id'] == self.order.pk)
        self.assertEqual(row['cash_qr_code'], self.token)

    def test_patch_delivered_allowed_for_cash(self):
        from apps.realtime.models import Notification

        Group.objects.get_or_create(name=UserGroup.COURIER.value)
        client = APIClient()
        client.force_authenticate(user=self.courier)
        with self.captureOnCommitCallbacks(execute=True):
            resp = client.patch(
                f'/api/v1/orders/{self.order.pk}/status/',
                {'status': 'delivered'},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], OrderStatus.DELIVERED.value)
        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                type='order_delivered',
            ).exists(),
        )

    def test_patch_completed_blocked(self):
        self._mark_delivered()
        client = APIClient()
        client.force_authenticate(user=self.courier)
        resp = client.patch(
            f'/api/v1/orders/{self.order.pk}/status/',
            {'status': 'completed'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get('code'), 'cash_use_qr_confirm')

    def test_generate_token_unique(self):
        a = generate_cash_qr_token()
        b = generate_cash_qr_token()
        self.assertNotEqual(a, b)

    def test_customer_delivery_response_api(self):
        from apps.realtime.models import Notification
        from apps.core.enums import UserGroup

        Group.objects.get_or_create(name=UserGroup.OPERATOR.value)
        operator = CustomUser.objects.create_user(phone='998901212121', password='x')
        operator.groups.add(Group.objects.get(name=UserGroup.OPERATOR.value))

        self._mark_delivered()
        confirm_cash_delivery_by_qr(
            order_id=self.order.pk,
            qr_code=self.token,
            courier_user=self.courier,
        )
        client = APIClient()
        client.force_authenticate(user=self.customer)
        with self.captureOnCommitCallbacks(execute=True):
            resp = client.post(
                f'/api/v1/orders/{self.order.pk}/delivery-response/',
                {'accepted': True},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(
                user=operator,
                type='staff_customer_delivery_response',
            ).exists(),
        )
        self.assertTrue(resp.data['accepted'])
        self.order.refresh_from_db()
        self.assertTrue(self.order.customer_delivery_accepted)
        self.assertIsNotNone(self.order.customer_delivery_responded_at)
