"""
CLICK Shop API (Prepare / Complete) and payment URL builder.
https://docs.click.uz/click-api-request/
"""
from __future__ import annotations

import hashlib
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.enums import OrderStatus, PaymentStatus, PaymentType
from apps.orders.models import ClickPayment, Order

logger = logging.getLogger(__name__)

CLICK_ERR_SUCCESS = 0
CLICK_ERR_SIGN = -1
CLICK_ERR_AMOUNT = -2
CLICK_ERR_NOT_FOUND = -5
CLICK_ERR_NO_TRANSACTION = -6
CLICK_ERR_ALREADY_PAID = -4
CLICK_ERR_CANCELLED = -9


def _click_settings() -> Dict[str, Any]:
    return {
        'service_id': int(getattr(settings, 'CLICK_SERVICE_ID', 0) or 0),
        'merchant_id': int(getattr(settings, 'CLICK_MERCHANT_ID', 0) or 0),
        'secret_key': str(getattr(settings, 'CLICK_SECRET_KEY', '') or ''),
        'merchant_user_id': getattr(settings, 'CLICK_MERCHANT_USER_ID', None),
        'pay_url': getattr(settings, 'CLICK_PAY_URL', 'https://my.click.uz/services/pay'),
        'return_url': getattr(settings, 'CLICK_RETURN_URL', '') or '',
    }


def amount_to_click_str(amount: Decimal) -> str:
    return f'{amount.quantize(Decimal("0.01")):.2f}'


def build_click_payment_url(
    *,
    order_id: int,
    amount: Decimal,
    merchant_user_id: Optional[int] = None,
    return_url: Optional[str] = None,
) -> str:
    cfg = _click_settings()
    if not cfg['service_id'] or not cfg['merchant_id']:
        raise ValueError('CLICK_SERVICE_ID and CLICK_MERCHANT_ID must be configured')

    params = {
        'service_id': cfg['service_id'],
        'merchant_id': cfg['merchant_id'],
        'amount': amount_to_click_str(amount),
        'transaction_param': str(order_id),
    }
    muid = merchant_user_id if merchant_user_id is not None else cfg['merchant_user_id']
    if muid:
        params['merchant_user_id'] = int(muid)
    ret = (return_url or cfg['return_url'] or '').strip()
    if ret:
        params['return_url'] = ret
    return f"{cfg['pay_url']}?{urlencode(params)}"


def _md5_hex(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def verify_prepare_sign(params: Mapping[str, Any]) -> bool:
    cfg = _click_settings()
    secret = cfg['secret_key']
    if not secret:
        return False
    expected = _md5_hex(
        f"{params.get('click_trans_id')}"
        f"{params.get('service_id')}"
        f"{secret}"
        f"{params.get('merchant_trans_id')}"
        f"{params.get('amount')}"
        f"{params.get('action')}"
        f"{params.get('sign_time')}"
    )
    return expected == str(params.get('sign_string', ''))


def verify_complete_sign(params: Mapping[str, Any]) -> bool:
    cfg = _click_settings()
    secret = cfg['secret_key']
    if not secret:
        return False
    expected = _md5_hex(
        f"{params.get('click_trans_id')}"
        f"{params.get('service_id')}"
        f"{secret}"
        f"{params.get('merchant_trans_id')}"
        f"{params.get('merchant_prepare_id')}"
        f"{params.get('amount')}"
        f"{params.get('action')}"
        f"{params.get('sign_time')}"
    )
    return expected == str(params.get('sign_string', ''))


def _parse_amount(raw: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(raw)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _order_payable_checkout(order: Order) -> Tuple[bool, str]:
    if order.payment_type != PaymentType.CARD.value:
        return False, 'Order is not card payment'
    if order.payment_status == PaymentStatus.PAID.value:
        return False, 'Order already paid'
    if order.status not in (OrderStatus.CREATED.value,):
        return False, 'Order is not awaiting payment'
    if order.is_deleted:
        return False, 'Order not found'
    return True, ''


def _order_payable_extra(order: Order) -> Tuple[bool, str]:
    from apps.orders.services.cash_delivery import extra_payment_due

    if order.payment_type != PaymentType.CARD.value:
        return False, 'Order is not card payment'
    if order.payment_status != PaymentStatus.PAID.value:
        return False, 'Initial payment required'
    if order.status in (
        OrderStatus.COMPLETED.value,
        OrderStatus.CANCELLED.value,
        OrderStatus.REJECTED.value,
        OrderStatus.CREATED.value,
    ):
        return False, 'Order is not ready for extra payment'
    if extra_payment_due(order) <= 0:
        return False, 'No extra payment due'
    if order.is_deleted:
        return False, 'Order not found'
    return True, ''


def _click_response(
  *,
    click_trans_id: Any,
    merchant_trans_id: Any,
    merchant_prepare_id: Optional[int] = None,
    merchant_confirm_id: Optional[int] = None,
    error: int,
    error_note: str,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        'click_trans_id': int(click_trans_id) if click_trans_id is not None else 0,
        'merchant_trans_id': str(merchant_trans_id or ''),
        'error': error,
        'error_note': error_note,
    }
    if merchant_prepare_id is not None:
        data['merchant_prepare_id'] = int(merchant_prepare_id)
    if merchant_confirm_id is not None:
        data['merchant_confirm_id'] = int(merchant_confirm_id)
    return data


def handle_click_prepare(params: Mapping[str, Any]) -> Dict[str, Any]:
    click_trans_id = params.get('click_trans_id')
    merchant_trans_id = params.get('merchant_trans_id')
    amount_raw = params.get('amount')
    action = str(params.get('action', ''))

    if action != '0':
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NO_TRANSACTION,
            error_note='Action not found',
        )

    if not verify_prepare_sign(params):
        logger.warning('CLICK prepare sign failed order=%s trans=%s', merchant_trans_id, click_trans_id)
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_SIGN,
            error_note='SIGN CHECK FAILED!',
        )

    cfg = _click_settings()
    if str(params.get('service_id')) != str(cfg['service_id']):
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NOT_FOUND,
            error_note='Invalid service_id',
        )

    try:
        order_id = int(merchant_trans_id)
    except (TypeError, ValueError):
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NOT_FOUND,
            error_note='User does not exist',
        )

    amount = _parse_amount(amount_raw)
    if amount is None:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_AMOUNT,
            error_note='Incorrect parameter amount',
        )

    try:
        order = Order.objects.get(pk=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NOT_FOUND,
            error_note='User does not exist',
        )

    from apps.orders.services.cash_delivery import extra_payment_due

    checkout_expected = order.estimated_total.quantize(Decimal('0.01'))
    extra_expected = (
        extra_payment_due(order).quantize(Decimal('0.01'))
        if order.payment_status == PaymentStatus.PAID.value
        else Decimal('0.00')
    )

    if amount == checkout_expected and order.payment_status != PaymentStatus.PAID.value:
        ok, reason = _order_payable_checkout(order)
        if not ok:
            return _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                error=CLICK_ERR_NOT_FOUND,
                error_note=reason,
            )
        expected = checkout_expected
        payment_kind = 'checkout'
    elif extra_expected > 0 and amount == extra_expected:
        ok, reason = _order_payable_extra(order)
        if not ok:
            return _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                error=CLICK_ERR_NOT_FOUND,
                error_note=reason,
            )
        expected = extra_expected
        payment_kind = 'extra'
    elif order.payment_status == PaymentStatus.PAID.value and extra_expected <= 0:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=order.pk,
            error=CLICK_ERR_ALREADY_PAID,
            error_note='Already paid',
        )
    else:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_AMOUNT,
            error_note='Incorrect parameter amount',
        )

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        existing = (
            ClickPayment.objects.select_for_update()
            .filter(click_trans_id=click_trans_id)
            .first()
        )
        if existing:
            return _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=existing.pk,
                error=CLICK_ERR_SUCCESS,
                error_note='Success',
            )

        paydoc = None
        if params.get('click_paydoc_id') not in (None, ''):
            try:
                paydoc = int(params['click_paydoc_id'])
            except (TypeError, ValueError):
                paydoc = None

        payment = ClickPayment.objects.create(
            order=order,
            amount=expected,
            click_trans_id=int(click_trans_id),
            click_paydoc_id=paydoc,
            state=ClickPayment.State.PREPARED,
            prepared_at=timezone.now(),
        )
        payment.last_error_note = payment_kind
        payment.save(update_fields=['last_error_note', 'updated_at'])

    logger.info('CLICK prepare ok order=%s payment=%s trans=%s', order_id, payment.pk, click_trans_id)
    return _click_response(
        click_trans_id=click_trans_id,
        merchant_trans_id=merchant_trans_id,
        merchant_prepare_id=payment.pk,
        error=CLICK_ERR_SUCCESS,
        error_note='Success',
    )


def _confirm_order_paid(order: Order, payment: ClickPayment, *, click_trans_id: Any) -> None:
    from apps.orders.pricing import (
        compute_order_settlement,
        mark_order_paid_amount,
        snapshot_order_checkout_total,
    )
    from apps.orders.services.cash_delivery import assign_delivery_qr_token

    kind = (payment.last_error_note or 'checkout').strip() or 'checkout'

    if kind == 'extra':
        compute_order_settlement(order)
        baseline = Decimal(str(order.paid_amount or 0)).quantize(Decimal('0.01'))
        order.paid_amount = (baseline + payment.amount).quantize(Decimal('0.01'))
        order.adjustment_balance = Decimal('0.00')
        order.refund_amount = Decimal('0.00')
        order.save(
            update_fields=[
                'paid_amount',
                'adjustment_balance',
                'refund_amount',
                'updated_at',
            ],
        )
    else:
        order.payment_status = PaymentStatus.PAID.value
        order.status = OrderStatus.CONFIRMED.value
        snapshot_order_checkout_total(order)
        mark_order_paid_amount(order)
        order.save(
            update_fields=[
                'payment_status',
                'status',
                'original_estimated_total',
                'paid_amount',
                'updated_at',
            ],
        )
        assign_delivery_qr_token(order)
        from apps.realtime.services.order_notifications import on_order_click_paid

        on_order_click_paid(order.pk)

    payment.state = ClickPayment.State.COMPLETED
    payment.completed_at = timezone.now()
    payment.click_trans_id = int(click_trans_id)
    payment.save(update_fields=['state', 'completed_at', 'click_trans_id', 'updated_at'])


def handle_click_complete(params: Mapping[str, Any]) -> Dict[str, Any]:
    click_trans_id = params.get('click_trans_id')
    merchant_trans_id = params.get('merchant_trans_id')
    merchant_prepare_id = params.get('merchant_prepare_id')
    amount_raw = params.get('amount')
    action = str(params.get('action', ''))
    click_error = int(params.get('error') or 0)

    if action != '1':
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NO_TRANSACTION,
            error_note='Action not found',
        )

    if not verify_complete_sign(params):
        logger.warning('CLICK complete sign failed order=%s trans=%s', merchant_trans_id, click_trans_id)
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_SIGN,
            error_note='SIGN CHECK FAILED!',
        )

    try:
        payment_id = int(merchant_prepare_id)
    except (TypeError, ValueError):
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NO_TRANSACTION,
            error_note='Transaction does not exist',
        )

    amount = _parse_amount(amount_raw)

    try:
        payment = ClickPayment.objects.select_related('order').get(pk=payment_id)
    except ClickPayment.DoesNotExist:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NO_TRANSACTION,
            error_note='Transaction does not exist',
        )

    order = payment.order
    if str(merchant_trans_id) != str(order.pk):
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_NOT_FOUND,
            error_note='User does not exist',
        )

    if payment.state == ClickPayment.State.COMPLETED:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_confirm_id=payment.pk,
            error=CLICK_ERR_ALREADY_PAID,
            error_note='Already paid',
        )

    if payment.state == ClickPayment.State.CANCELLED:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_CANCELLED,
            error_note='Transaction cancelled',
        )

    if amount is not None and amount != payment.amount:
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            error=CLICK_ERR_AMOUNT,
            error_note='Incorrect parameter amount',
        )

    if click_error < 0:
        with transaction.atomic():
            payment = ClickPayment.objects.select_for_update().get(pk=payment.pk)
            payment.state = ClickPayment.State.CANCELLED
            payment.last_error_code = click_error
            payment.last_error_note = str(params.get('error_note') or '')
            payment.save(update_fields=['state', 'last_error_code', 'last_error_note', 'updated_at'])
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_confirm_id=payment.pk,
            error=CLICK_ERR_CANCELLED,
            error_note='Transaction cancelled',
        )

    with transaction.atomic():
        payment = ClickPayment.objects.select_for_update().get(pk=payment.pk)
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        payment_kind = (payment.last_error_note or 'checkout').strip() or 'checkout'
        if order.payment_status == PaymentStatus.PAID.value and payment_kind != 'extra':
            payment.state = ClickPayment.State.COMPLETED
            payment.completed_at = timezone.now()
            payment.save(update_fields=['state', 'completed_at', 'updated_at'])
            return _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_confirm_id=payment.pk,
                error=CLICK_ERR_ALREADY_PAID,
                error_note='Already paid',
            )
        _confirm_order_paid(order, payment, click_trans_id=click_trans_id)

    logger.info('CLICK complete ok order=%s payment=%s trans=%s', order.pk, payment.pk, click_trans_id)
    return _click_response(
        click_trans_id=click_trans_id,
        merchant_trans_id=merchant_trans_id,
        merchant_confirm_id=payment.pk,
        error=CLICK_ERR_SUCCESS,
        error_note='Success',
    )
