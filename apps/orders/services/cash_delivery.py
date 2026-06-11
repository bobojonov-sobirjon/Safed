"""Delivery QR: cash (to‘lov kuryerda) va card (oldindan to‘langan + qo‘shimcha Click)."""
from __future__ import annotations

import logging
import secrets
from decimal import Decimal, ROUND_CEILING
from typing import Any, Dict, Tuple

from django.db import transaction
from django.utils import timezone

from apps.core.enums import OrderStatus, PaymentStatus, PaymentType
from apps.orders.models import Order, OrderCourier, OrderProduct
from apps.orders.pricing import compute_order_settlement, mark_order_paid_amount
from apps.products.unit_pricing import stock_units_required

from .delivery_events import (
    EVENT_COURIER_CONFIRMED,
    broadcast_order_delivery_event,
)

logger = logging.getLogger(__name__)

DELIVERY_QR_CONFIRM_STATUSES = (OrderStatus.DELIVERED.value,)

CARD_QR_VISIBLE_STATUSES = (
    OrderStatus.CONFIRMED.value,
    OrderStatus.PICKING.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.DELIVERED.value,
)


class CashDeliveryError(Exception):
    def __init__(self, message: str, *, code: str = 'invalid'):
        self.message = message
        self.code = code
        super().__init__(message)


def generate_cash_qr_token() -> str:
    return secrets.token_urlsafe(32)


def assign_delivery_qr_token(order: Order) -> str:
    """Cash va card buyurtmalar uchun bitta martalik completion QR."""
    if order.cash_qr_token:
        return order.cash_qr_token
    from apps.orders.cash_qr import render_cash_qr_file

    token = generate_cash_qr_token()
    order.cash_qr_token = token
    png = render_cash_qr_file(token, filename=f'order_{order.pk}.png')
    order.cash_qr_image.save(f'order_{order.pk}.png', png, save=False)
    order.save(update_fields=['cash_qr_token', 'cash_qr_image', 'updated_at'])
    logger.info('Delivery QR saved order=%s path=%s', order.pk, order.cash_qr_image.name)
    return token


def assign_cash_qr_token(order: Order) -> str:
    return assign_delivery_qr_token(order)


def extra_payment_due(order: Order) -> Decimal:
    """Yig‘ishdan keyin mijozdan qo‘shimcha Click to‘lovi (card)."""
    compute_order_settlement(order)
    adj = Decimal(str(order.adjustment_balance or 0)).quantize(Decimal('0.01'))
    return adj if adj > 0 else Decimal('0.00')


def delivery_qr_visible_for_customer(order: Order) -> bool:
    if not order.cash_qr_token:
        return False
    if order.status in (
        OrderStatus.COMPLETED.value,
        OrderStatus.CANCELLED.value,
        OrderStatus.REJECTED.value,
    ):
        return False
    if order.payment_type == PaymentType.CASH.value:
        return order.payment_status == PaymentStatus.PENDING.value
    if order.payment_type == PaymentType.CARD.value:
        return (
            order.payment_status == PaymentStatus.PAID.value
            and order.status in CARD_QR_VISIBLE_STATUSES
        )
    return False


def ensure_cash_qr_image(order: Order) -> None:
    """Eski buyurtmalar: token bor, rasm yo‘q — qayta generatsiya."""
    if not order.cash_qr_token:
        return
    if order.cash_qr_image:
        return
    from apps.orders.cash_qr import render_cash_qr_file

    png = render_cash_qr_file(order.cash_qr_token, filename=f'order_{order.pk}.png')
    order.cash_qr_image.save(f'order_{order.pk}.png', png, save=True)


def deduct_order_stock(order: Order) -> None:
    from apps.inventory.services.stock import adjust_product_stock

    products_qs = OrderProduct.objects.select_related('product').filter(order=order)
    for op in products_qs:
        if not op.product:
            continue
        norm = op.normalized_quantity if op.normalized_quantity is not None else op.quantity
        needed = stock_units_required(op.product, norm)
        dec = int(needed.to_integral_value(rounding=ROUND_CEILING))
        if dec <= 0:
            continue
        adjust_product_stock(op.product_id, -dec)


def _finalize_delivery_qr_confirm(order: Order, *, courier_user) -> Dict[str, Any]:
    now = timezone.now()
    if order.cash_qr_image:
        order.cash_qr_image.delete(save=False)
    order.cash_qr_token = None
    order.qr_confirmed_at = now
    if not order.delivered_at:
        order.delivered_at = now
    previous_status = order.status
    order.status = OrderStatus.COMPLETED.value
    compute_order_settlement(order)
    if order.payment_type == PaymentType.CARD.value:
        order.paid_amount = (order.final_total or order.estimated_total).quantize(Decimal('0.01'))
        if Decimal(str(order.adjustment_balance or 0)) > 0:
            order.adjustment_balance = Decimal('0.00')
    order.save(
        update_fields=[
            'cash_qr_token',
            'cash_qr_image',
            'qr_confirmed_at',
            'delivered_at',
            'status',
            'payment_status',
            'paid_amount',
            'final_total',
            'adjustment_balance',
            'refund_amount',
            'updated_at',
        ],
    )
    deduct_order_stock(order)
    from apps.orders.services.cashback import accrue_order_cashback

    accrue_order_cashback(order)

    payload = {
        'order_id': order.pk,
        'payment_type': order.payment_type,
        'message': (
            'Курьер подтвердил доставку. Вы получили заказ? '
            'Подтвердите получение в приложении.'
        ),
        'payment_status': order.payment_status,
        'status': order.status,
        'delivered_at': order.delivered_at.isoformat() if order.delivered_at else None,
        'estimated_total': str(order.estimated_total),
        'final_total': str(order.final_total) if order.final_total is not None else None,
    }
    broadcast_order_delivery_event(
        order_id=order.pk,
        event=EVENT_COURIER_CONFIRMED,
        data=payload,
        include_customer=True,
        include_couriers=False,
    )
    from apps.realtime.services.order_notifications import on_cash_confirmed, on_status_changed

    on_cash_confirmed(order.pk)
    on_status_changed(order.pk, OrderStatus.COMPLETED.value, previous_status)
    logger.info(
        'Delivery QR confirmed order=%s courier=%s type=%s',
        order.pk,
        courier_user.pk,
        order.payment_type,
    )
    return {
        'order_id': order.pk,
        'payment_status': order.payment_status,
        'status': order.status,
        'delivered_at': order.delivered_at.isoformat() if order.delivered_at else None,
    }


@transaction.atomic
def confirm_cash_delivery_by_qr(
    *,
    order_id: int,
    qr_code: str,
    courier_user,
) -> Tuple[Order, Dict[str, Any]]:
    code = (qr_code or '').strip()
    if not code:
        raise CashDeliveryError('QR code talab qilinadi.', code='qr_code')

    order = (
        Order.objects.select_for_update()
        .select_related('user')
        .get(pk=order_id, is_deleted=False)
    )

    if order.status == OrderStatus.COMPLETED.value:
        raise CashDeliveryError('Buyurtma allaqachon yakunlangan.', code='already_completed')

    if order.status not in DELIVERY_QR_CONFIRM_STATUSES:
        raise CashDeliveryError(
            'Avval kuryer statusni delivered qiladi, keyin QR skaner qilinadi.',
            code='status',
        )

    is_assigned = OrderCourier.objects.filter(order_id=order.pk, courier_id=courier_user.pk).exists()
    if not is_assigned:
        raise CashDeliveryError('Siz bu buyurtmaga biriktirilmagansiz.', code='courier')

    if not order.cash_qr_token or order.cash_qr_token != code:
        raise CashDeliveryError('QR code noto‘g‘ri yoki muddati tugagan.', code='qr_mismatch')

    if order.payment_type == PaymentType.CASH.value:
        if order.payment_status == PaymentStatus.PAID.value:
            raise CashDeliveryError('Buyurtma allaqachon to‘langan.', code='already_paid')
        order.payment_status = PaymentStatus.PAID.value
        mark_order_paid_amount(order)
    elif order.payment_type == PaymentType.CARD.value:
        if order.payment_status != PaymentStatus.PAID.value:
            raise CashDeliveryError(
                'Karta buyurtmasi avval Click orqali to‘lanishi kerak.',
                code='not_prepaid',
            )
        due = extra_payment_due(order)
        if due > 0:
            raise CashDeliveryError(
                f'Qo‘shimcha to‘lov kerak: {due} UZS. Mijoz POST /orders/{{id}}/click-payment/ orqali to‘lasin.',
                code='extra_payment_required',
            )
        from apps.orders.services.click_refund import sync_order_click_refund

        refund_result = sync_order_click_refund(order.pk)
        if refund_result.get('status') == 'failed':
            logger.warning(
                'CLICK refund failed at delivery confirm order=%s result=%s',
                order.pk,
                refund_result,
            )
    else:
        raise CashDeliveryError('Noma’lum to‘lov turi.', code='payment_type')

    summary = _finalize_delivery_qr_confirm(order, courier_user=courier_user)
    return order, summary


@transaction.atomic
def record_customer_delivery_response(
    *,
    order: Order,
    accepted: bool,
    user,
) -> Dict[str, Any]:
    if order.user_id != user.pk:
        raise CashDeliveryError('Faqat buyurtma egasi javob bera oladi.', code='forbidden')

    if order.payment_type not in (PaymentType.CASH.value, PaymentType.CARD.value):
        raise CashDeliveryError('Faqat cash yoki card buyurtma.', code='payment_type')

    if order.status != OrderStatus.COMPLETED.value:
        raise CashDeliveryError('Buyurtma hali yakunlanmagan.', code='status')

    if order.customer_delivery_responded_at is not None:
        raise CashDeliveryError('Javob allaqachon yuborilgan.', code='already_responded')

    order = Order.objects.select_for_update().get(pk=order.pk)
    now = timezone.now()
    order.customer_delivery_accepted = accepted
    order.customer_delivery_responded_at = now
    order.save(
        update_fields=['customer_delivery_accepted', 'customer_delivery_responded_at', 'updated_at'],
    )

    from apps.realtime.services.order_notifications import on_customer_delivery_response

    on_customer_delivery_response(order.pk, accepted=accepted)

    logger.info('Customer delivery response order=%s accepted=%s', order.pk, accepted)
    return {
        'order_id': order.pk,
        'accepted': accepted,
        'message': 'Mijoz mahsulotni oldi' if accepted else 'Mijoz rad etdi',
        'responded_at': now.isoformat(),
    }
