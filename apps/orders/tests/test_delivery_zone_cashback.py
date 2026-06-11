from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.orders.models import CashbackSettings, DeliveryZone, Order
from apps.orders.services.cashback import accrue_order_cashback, compute_cashback_amount
from apps.orders.services.delivery_zone import is_location_in_delivery_zone, validate_delivery_location

User = get_user_model()


class DeliveryZoneTests(TestCase):
    def setUp(self):
        DeliveryZone.objects.create(
            name='Markaz',
            address='Toshkent markaz',
            lat=Decimal('41.311081'),
            long=Decimal('69.240562'),
            radius_m=5000,
            is_active=True,
        )

    def test_inside_zone(self):
        self.assertTrue(is_location_in_delivery_zone(Decimal('41.312'), Decimal('69.241')))
        self.assertIsNone(validate_delivery_location(Decimal('41.312'), Decimal('69.241')))

    def test_outside_zone(self):
        self.assertFalse(is_location_in_delivery_zone(Decimal('40.0'), Decimal('70.0')))
        self.assertIsNotNone(validate_delivery_location(Decimal('40.0'), Decimal('70.0')))


class CashbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='+998901112233', password='pass')
        CashbackSettings.objects.create(pk=1, cashback_percent=Decimal('5.00'), is_active=True)
        self.order = Order.objects.create(
            user=self.user,
            estimated_total=Decimal('100000.00'),
            final_total=Decimal('100000.00'),
        )

    def test_compute_cashback(self):
        amount = compute_cashback_amount(self.order)
        self.assertEqual(amount, Decimal('5000.00'))

    def test_accrue_updates_user_balance(self):
        accrue_order_cashback(self.order)
        self.user.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.user.cashback_balance, Decimal('5000.00'))
        self.assertEqual(self.order.cashback_earned, Decimal('5000.00'))
        accrue_order_cashback(self.order)
        self.user.refresh_from_db()
        self.assertEqual(self.user.cashback_balance, Decimal('5000.00'))
