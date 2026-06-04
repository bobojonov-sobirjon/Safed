"""CLICK refund after picking settlement (partial / full reversal)."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.enums import PaymentStatus, PaymentType
from apps.orders.models import ClickPayment, ClickRefund, Order
from apps.orders.pricing import compute_order_settlement
from apps.orders.services.click_merchant import (
    ClickMerchantError,
    click_refund_auto_enabled,
    full_reversal,
    merchant_api_configured,
    partial_reversal,
    resolve_click_payment_id,
)

logger = logging.getLogger(__name__)


class ClickRefundError(Exception):
    def __init__(self, message: str, *, code: str = 'invalid'):
        self.message = message
        self.code = code
        super().__init__(message)


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _payment_kind(payment: ClickPayment) -> str:
    kind = (payment.last_error_note or 'checkout').strip().lower()
    return 'extra' if kind == 'extra' else 'checkout'


def _refundable_payments(order: Order) -> List[ClickPayment]:
    payments = list(
        order.click_payments.filter(state=ClickPayment.State.COMPLETED).order_by('created_at')
    )
    payments.sort(key=lambda p: (0 if _payment_kind(p) == 'checkout' else 1, p.created_at))
    return payments


def _refunded_on_payment(payment: ClickPayment) -> Decimal:
    total = (
        ClickRefund.objects.filter(
            source_payment=payment,
            state=ClickRefund.State.COMPLETED,
        ).aggregate(total=Sum('amount'))['total']
    )
    return _d(total).quantize(Decimal('0.01'))


def _payment_click_id(payment: ClickPayment) -> int:
    return resolve_click_payment_id(
        click_paydoc_id=payment.click_paydoc_id,
        click_trans_id=payment.click_trans_id,
    )


def refund_target_amount(order: Order) -> Decimal:
    compute_order_settlement(order)
    return _d(order.refund_amount).quantize(Decimal('0.01'))


def refunded_total(order: Order) -> Decimal:
    total = (
        ClickRefund.objects.filter(
            order=order,
            state=ClickRefund.State.COMPLETED,
        ).aggregate(total=Sum('amount'))['total']
    )
    return _d(total).quantize(Decimal('0.01'))


def pending_refund_amount(order: Order) -> Decimal:
    """Hali CLICK orqali qaytarilmagan summa (settlement adjustment_balance)."""
    compute_order_settlement(order)
    unsettled = _d(order.adjustment_balance).quantize(Decimal('0.01'))
    if unsettled >= 0:
        return Decimal('0.00')
    return abs(unsettled).quantize(Decimal('0.01'))


def _apply_refund_to_order(order: Order, refunded: Decimal) -> None:
    paid = _d(order.paid_amount).quantize(Decimal('0.01'))
    order.paid_amount = (paid - refunded).quantize(Decimal('0.01'))
    compute_order_settlement(order)
    if _d(order.adjustment_balance) <= 0:
        order.adjustment_balance = Decimal('0.00')
    order.save(
        update_fields=[
            'paid_amount',
            'adjustment_balance',
            'refund_amount',
            'final_total',
            'updated_at',
        ],
    )


def _execute_reversal(*, payment: ClickPayment, amount: Decimal) -> None:
    click_id = _payment_click_id(payment)
    already = _refunded_on_payment(payment)
    remaining = (_d(payment.amount) - already).quantize(Decimal('0.01'))
    if remaining <= 0:
        raise ClickRefundError('To‘lov bo‘yicha qaytarish limiti tugagan.', code='limit')

    to_refund = min(amount, remaining).quantize(Decimal('0.01'))
    if to_refund <= 0:
        return

    if to_refund == remaining and to_refund == _d(payment.amount).quantize(Decimal('0.01')):
        full_reversal(click_id)
    else:
        partial_reversal(click_id, to_refund)


@transaction.atomic
def _create_and_process_refund(
    *,
    order: Order,
    payment: ClickPayment,
    amount: Decimal,
) -> ClickRefund:
    order = Order.objects.select_for_update().get(pk=order.pk)
    amount = amount.quantize(Decimal('0.01'))
    if amount <= 0:
        raise ClickRefundError('Qaytarish summasi 0 dan katta bo‘lishi kerak.', code='amount')

    idempotency_key = (
        f'order-{order.pk}-payment-{payment.pk}-'
        f'amount-{amount}-adj-{_d(order.adjustment_balance).quantize(Decimal("0.01"))}'
    )
    existing = ClickRefund.objects.filter(idempotency_key=idempotency_key).first()
    if existing and existing.state == ClickRefund.State.COMPLETED:
        return existing

    refund = existing or ClickRefund.objects.create(
        order=order,
        source_payment=payment,
        amount=amount,
        click_payment_id=_payment_click_id(payment),
        idempotency_key=idempotency_key,
        state=ClickRefund.State.PROCESSING,
    )
    if refund.state != ClickRefund.State.PROCESSING:
        refund.state = ClickRefund.State.PROCESSING
        refund.save(update_fields=['state'])

    try:
        _execute_reversal(payment=payment, amount=amount)
    except ClickMerchantError as exc:
        refund.state = ClickRefund.State.FAILED
        refund.error_code = exc.error_code
        refund.error_note = exc.message[:255]
        refund.save(update_fields=['state', 'error_code', 'error_note'])
        raise

    refund.state = ClickRefund.State.COMPLETED
    refund.error_code = 0
    refund.error_note = 'Success'
    refund.completed_at = timezone.now()
    refund.save(
        update_fields=['state', 'error_code', 'error_note', 'completed_at'],
    )
    _apply_refund_to_order(order, amount)
    return refund


def sync_order_click_refund(order_id: int) -> Dict[str, Any]:
    """
    Yig‘ishdan keyin settlement bo‘yicha CLICK orqali qaytarish.
    Incremental: avvalgi muvaffaqiyatli refundlardan keyin qolgan delta qaytariladi.
    """
    if not click_refund_auto_enabled():
        return {'status': 'disabled'}

    try:
        order = Order.objects.select_related('user').get(pk=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return {'status': 'not_found'}

    if order.payment_type != PaymentType.CARD.value:
        return {'status': 'skipped', 'reason': 'not_card'}
    if order.payment_status != PaymentStatus.PAID.value:
        return {'status': 'skipped', 'reason': 'not_paid'}
    if not merchant_api_configured():
        logger.warning('CLICK refund skipped: merchant API not configured order=%s', order_id)
        return {'status': 'skipped', 'reason': 'not_configured'}

    delta = pending_refund_amount(order)
    if delta <= 0:
        return {'status': 'none', 'refund_amount': '0.00'}

    payments = _refundable_payments(order)
    if not payments:
        logger.warning('CLICK refund skipped: no completed payments order=%s', order_id)
        return {'status': 'skipped', 'reason': 'no_payment'}

    processed: List[Dict[str, Any]] = []
    remaining = delta

    try:
        for payment in payments:
            if remaining <= 0:
                break
            already = _refunded_on_payment(payment)
            capacity = (_d(payment.amount) - already).quantize(Decimal('0.01'))
            if capacity <= 0:
                continue
            chunk = min(remaining, capacity).quantize(Decimal('0.01'))
            refund = _create_and_process_refund(order=order, payment=payment, amount=chunk)
            processed.append(
                {
                    'refund_id': refund.pk,
                    'payment_id': payment.pk,
                    'amount': str(chunk),
                },
            )
            remaining = (remaining - chunk).quantize(Decimal('0.01'))
    except (ClickMerchantError, ClickRefundError) as exc:
        logger.warning('CLICK refund failed order=%s: %s', order_id, exc)
        return {
            'status': 'failed',
            'error': getattr(exc, 'message', str(exc)),
            'processed': processed,
            'pending_amount': str(remaining),
        }

    if remaining > 0:
        return {
            'status': 'partial',
            'processed': processed,
            'pending_amount': str(remaining),
        }

    order.refresh_from_db()
    from apps.realtime.services.order_notifications import on_click_refund_processed

    on_click_refund_processed(order_id, str(delta))
    return {
        'status': 'completed',
        'refunded_amount': str(delta),
        'processed': processed,
    }


def schedule_order_click_refund(order_id: int) -> None:
    from apps.realtime.services.order_notifications import schedule_after_commit

    schedule_after_commit(lambda: sync_order_click_refund(order_id))


def build_refund_status_payload(order: Order) -> Dict[str, Any]:
    target = refund_target_amount(order)
    done = refunded_total(order)
    pending = pending_refund_amount(order)
    latest = (
        ClickRefund.objects.filter(order=order)
        .order_by('-created_at')
        .values('state', 'error_note', 'amount', 'completed_at')
        .first()
    )
    return {
        'refund_target': str(target),
        'refund_processed': str(done),
        'refund_pending': str(pending),
        'latest_refund': latest,
    }
