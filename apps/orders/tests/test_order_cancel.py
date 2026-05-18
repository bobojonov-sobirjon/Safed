from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus
from apps.orders.models import Order, OrderCancelReason


class OrderCancelAPITests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(phone='998901111111', password='pass12345')
        self.other = CustomUser.objects.create_user(phone='998902222222', password='pass12345')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.reason = OrderCancelReason.objects.create(code='test_reason', sort_order=1, is_active=True)
        self.reason.set_current_language('uz')
        self.reason.name = 'Test'
        self.reason.save()
        self.reason.create_translation('ru', name='Тест')
        self.reason.create_translation('en', name='Test')
        self.order = Order.objects.create(
            user=self.user,
            status=OrderStatus.CREATED.value,
            products_subtotal=Decimal('1000.00'),
            estimated_total=Decimal('1000.00'),
        )

    def test_cancel_reasons_list(self):
        resp = self.client.get('/api/v1/orders/cancel-reasons/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(r['code'] == 'test_reason' for r in resp.data))

    def test_cancel_with_reasons_and_comment(self):
        resp = self.client.post(
            f'/api/v1/orders/{self.order.pk}/cancel/',
            {'reason_ids': [self.reason.pk], 'comment': 'Boshqa sabab'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], OrderStatus.CANCELLED.value)
        self.assertIsNotNone(resp.data['cancellation'])
        self.assertEqual(resp.data['cancellation']['comment'], 'Boshqa sabab')
        self.assertEqual(len(resp.data['cancellation']['reasons']), 1)
        self.assertFalse(resp.data['can_user_cancel'])

    def test_cancel_requires_comment_or_reasons(self):
        resp = self.client.post(f'/api/v1/orders/{self.order.pk}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_cancel_not_allowed_when_confirmed(self):
        self.order.status = OrderStatus.CONFIRMED.value
        self.order.save(update_fields=['status'])
        resp = self.client.post(
            f'/api/v1/orders/{self.order.pk}/cancel/',
            {'reason_ids': [self.reason.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_cancellation_null_when_active(self):
        resp = self.client.get(f'/api/v1/orders/{self.order.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['cancellation'])
