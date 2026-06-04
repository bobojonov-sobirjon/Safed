from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, PaymentStatus, PaymentType, UserGroup
from apps.orders.models import ClickPayment, ClickRefund, Order, OrderProduct
from apps.orders.services.click_refund import (
    pending_refund_amount,
    sync_order_click_refund,
)


@override_settings(
    CLICK_SERVICE_ID=101345,
    CLICK_MERCHANT_USER_ID=82888,
    CLICK_SECRET_KEY='test-secret',
    CLICK_REFUND_AUTO=True,
)
class ClickRefundSyncTests(TestCase):
    def setUp(self):
        self.customer = CustomUser.objects.create_user(phone='998901112233', password='pass12345')
        self.courier = CustomUser.objects.create_user(phone='998904445566', password='pass12345')
        Group.objects.get_or_create(name=UserGroup.COURIER.value)

        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.PICKING.value,
            payment_type=PaymentType.CARD.value,
            payment_status=PaymentStatus.PAID.value,
            products_subtotal=Decimal('80000'),
            estimated_total=Decimal('80000'),
            original_estimated_total=Decimal('100000'),
            paid_amount=Decimal('100000'),
            final_total=Decimal('80000'),
            refund_amount=Decimal('20000'),
            adjustment_balance=Decimal('-20000'),
        )
        self.payment = ClickPayment.objects.create(
            order=self.order,
            amount=Decimal('100000'),
            click_trans_id=999888777,
            click_paydoc_id=999888777,
            state=ClickPayment.State.COMPLETED,
            last_error_note='checkout',
        )

    @patch('apps.orders.services.click_refund.partial_reversal')
    def test_sync_partial_refund_after_picking(self, mock_partial):
        mock_partial.return_value = {'error_code': 0, 'error_note': 'Success'}

        result = sync_order_click_refund(self.order.pk)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['refunded_amount'], '20000.00')
        mock_partial.assert_called_once_with(999888777, Decimal('20000.00'))

        self.order.refresh_from_db()
        self.assertEqual(self.order.paid_amount, Decimal('80000.00'))
        self.assertEqual(self.order.adjustment_balance, Decimal('0.00'))

        refund = ClickRefund.objects.get(order=self.order)
        self.assertEqual(refund.state, ClickRefund.State.COMPLETED)
        self.assertEqual(refund.amount, Decimal('20000.00'))

    @patch('apps.orders.services.click_refund.partial_reversal')
    def test_sync_is_idempotent(self, mock_partial):
        mock_partial.return_value = {'error_code': 0, 'error_note': 'Success'}

        sync_order_click_refund(self.order.pk)
        result = sync_order_click_refund(self.order.pk)

        self.assertEqual(result['status'], 'none')
        mock_partial.assert_called_once()

    @patch('apps.orders.services.click_refund.full_reversal')
    def test_sync_full_refund_when_entire_payment_returned(self, mock_full):
        self.order.estimated_total = Decimal('0.00')
        self.order.final_total = Decimal('0.00')
        self.order.refund_amount = Decimal('100000')
        self.order.adjustment_balance = Decimal('-100000')
        self.order.save()

        mock_full.return_value = {'error_code': 0, 'error_note': 'Success'}

        result = sync_order_click_refund(self.order.pk)

        self.assertEqual(result['status'], 'completed')
        mock_full.assert_called_once_with(999888777)

    def test_pending_refund_amount(self):
        self.assertEqual(pending_refund_amount(self.order), Decimal('20000.00'))

    @patch('apps.orders.services.click_refund.partial_reversal')
    def test_sync_skips_non_card_orders(self, mock_partial):
        self.order.payment_type = PaymentType.CASH.value
        self.order.save()

        result = sync_order_click_refund(self.order.pk)

        self.assertEqual(result['status'], 'skipped')
        mock_partial.assert_not_called()


@override_settings(
    CLICK_SERVICE_ID=101345,
    CLICK_MERCHANT_USER_ID=82888,
    CLICK_SECRET_KEY='test-secret',
    CLICK_REFUND_AUTO=True,
)
class ClickRefundIncrementalTests(TestCase):
    """Ikki bosqichli yig‘ish: avval 8 ta, keyin yana kamaytirish."""

    def setUp(self):
        self.customer = CustomUser.objects.create_user(phone='998907778899', password='pass12345')
        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.PICKING.value,
            payment_type=PaymentType.CARD.value,
            payment_status=PaymentStatus.PAID.value,
            products_subtotal=Decimal('90000'),
            estimated_total=Decimal('90000'),
            original_estimated_total=Decimal('100000'),
            paid_amount=Decimal('90000'),
            final_total=Decimal('90000'),
            refund_amount=Decimal('10000'),
            adjustment_balance=Decimal('-10000'),
        )
        ClickPayment.objects.create(
            order=self.order,
            amount=Decimal('100000'),
            click_trans_id=111222333,
            state=ClickPayment.State.COMPLETED,
            last_error_note='checkout',
        )
        ClickRefund.objects.create(
            order=self.order,
            source_payment=self.order.click_payments.first(),
            amount=Decimal('10000'),
            click_payment_id=111222333,
            idempotency_key='existing-refund',
            state=ClickRefund.State.COMPLETED,
        )

    @patch('apps.orders.services.click_refund.partial_reversal')
    def test_only_refunds_delta(self, mock_partial):
        self.order.products_subtotal = Decimal('80000')
        self.order.estimated_total = Decimal('80000')
        self.order.final_total = Decimal('80000')
        self.order.refund_amount = Decimal('10000')
        self.order.adjustment_balance = Decimal('-10000')
        self.order.paid_amount = Decimal('90000')
        self.order.save()

        mock_partial.return_value = {'error_code': 0, 'error_note': 'Success'}
        result = sync_order_click_refund(self.order.pk)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['refunded_amount'], '10000.00')
        mock_partial.assert_called_once_with(111222333, Decimal('10000.00'))
