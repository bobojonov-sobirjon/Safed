from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, PaymentStatus, PaymentType, UserGroup
from apps.orders.models import Order, OrderCourier
from apps.orders.services.cash_delivery import (
    CashDeliveryError,
    assign_delivery_qr_token,
    confirm_cash_delivery_by_qr,
    extra_payment_due,
)


class CardDeliveryQrTests(TestCase):
    def setUp(self):
        self.customer = CustomUser.objects.create_user(phone='998905555555', password='pass12345')
        self.courier = CustomUser.objects.create_user(phone='998906666666', password='pass12345')
        Group.objects.get_or_create(name=UserGroup.COURIER.value)
        self.courier.groups.add(Group.objects.get(name=UserGroup.COURIER.value))

        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.DELIVERED.value,
            payment_type=PaymentType.CARD.value,
            payment_status=PaymentStatus.PAID.value,
            products_subtotal=Decimal('10000'),
            estimated_total=Decimal('10000'),
            original_estimated_total=Decimal('10000'),
            paid_amount=Decimal('10000'),
            final_total=Decimal('10000'),
            delivered_at=timezone.now(),
        )
        self.token = assign_delivery_qr_token(self.order)
        OrderCourier.objects.create(order=self.order, courier=self.courier)

    def test_card_confirm_without_extra_completes(self):
        order, _ = confirm_cash_delivery_by_qr(
            order_id=self.order.pk,
            qr_code=self.token,
            courier_user=self.courier,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED.value)
        self.assertIsNone(order.cash_qr_token)

    def test_card_confirm_blocks_when_extra_due(self):
        self.order.estimated_total = Decimal('12000')
        self.order.final_total = Decimal('12000')
        self.order.adjustment_balance = Decimal('2000')
        self.order.save()
        with self.assertRaises(CashDeliveryError) as ctx:
            confirm_cash_delivery_by_qr(
                order_id=self.order.pk,
                qr_code=self.token,
                courier_user=self.courier,
            )
        self.assertEqual(ctx.exception.code, 'extra_payment_required')
        self.assertEqual(extra_payment_due(self.order), Decimal('2000.00'))
