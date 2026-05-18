from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, PaymentStatus, PaymentType
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
        from django.contrib.auth.models import Group
        from apps.core.enums import UserGroup

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

    def test_confirm_success(self):
        order, summary = confirm_cash_delivery_by_qr(
            order_id=self.order.pk,
            qr_code=self.token,
            courier_user=self.courier,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DELIVERED.value)
        self.assertEqual(order.payment_status, PaymentStatus.PAID.value)
        self.assertIsNone(order.cash_qr_token)
        self.assertIsNotNone(order.qr_confirmed_at)
        self.assertIsNotNone(order.delivered_at)

    def test_confirm_invalid_qr(self):
        with self.assertRaises(CashDeliveryError):
            confirm_cash_delivery_by_qr(
                order_id=self.order.pk,
                qr_code='wrong-token',
                courier_user=self.courier,
            )

    def test_confirm_qr_single_use(self):
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

    def test_patch_delivered_blocked_for_cash(self):
        from django.contrib.auth.models import Group
        from apps.core.enums import UserGroup

        admin = CustomUser.objects.create_user(phone='998905555555', password='pass12345')
        Group.objects.get_or_create(name=UserGroup.ADMIN.value)
        admin.groups.add(Group.objects.get(name=UserGroup.ADMIN.value))
        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.patch(
            f'/api/v1/orders/{self.order.pk}/status/',
            {'status': 'delivered'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get('code'), 'cash_use_qr_confirm')

    def test_generate_token_unique(self):
        a = generate_cash_qr_token()
        b = generate_cash_qr_token()
        self.assertNotEqual(a, b)

    def test_customer_delivery_response_api(self):
        confirm_cash_delivery_by_qr(
            order_id=self.order.pk,
            qr_code=self.token,
            courier_user=self.courier,
        )
        client = APIClient()
        client.force_authenticate(user=self.customer)
        resp = client.post(
            f'/api/v1/orders/{self.order.pk}/delivery-response/',
            {'accepted': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['accepted'])
        self.order.refresh_from_db()
        self.assertTrue(self.order.customer_delivery_accepted)
        self.assertIsNotNone(self.order.customer_delivery_responded_at)

        resp2 = client.post(
            f'/api/v1/orders/{self.order.pk}/delivery-response/',
            {'accepted': False},
            format='json',
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertEqual(resp2.data.get('code'), 'already_responded')
