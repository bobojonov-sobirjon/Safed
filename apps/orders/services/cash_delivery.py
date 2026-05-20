"""Cash on delivery: QR generation, courier confirm, stock + settlement."""
from __future__ import annotations

import logging
import secrets
from decimal import Decimal, ROUND_CEILING
from typing import Any, Dict, Tuple

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.enums import OrderStatus, PaymentStatus, PaymentType
from apps.orders.models import Order, OrderCourier, OrderProduct
from apps.orders.pricing import compute_order_settlement, mark_order_paid_amount
from apps.products.models import Products
from apps.products.unit_pricing import stock_units_required

from .delivery_events import (
    EVENT_COURIER_CONFIRMED,
    broadcast_order_delivery_event,
)

logger = logging.getLogger(__name__)

CASH_QR_CONFIRM_STATUSES = (OrderStatus.DELIVERED.value,)


class CashDeliveryError(Exception):
    def __init__(self, message: str, *, code: str = 'invalid'):
        self.message = message
        self.code = code
        super().__init__(message)


def generate_cash_qr_token() -> str:
    return secrets.token_urlsafe(32)


def assign_cash_qr_token(order: Order) -> str:
    from apps.orders.cash_qr import render_cash_qr_file

    token = generate_cash_qr_token()
    order.cash_qr_token = token
    png = render_cash_qr_file(token, filename=f'order_{order.pk}.png')
    order.cash_qr_image.save(f'order_{order.pk}.png', png, save=False)
    order.save(update_fields=['cash_qr_token', 'cash_qr_image', 'updated_at'])
    logger.info('Cash QR saved order=%s path=%s', order.pk, order.cash_qr_image.name)
    return token


def ensure_cash_qr_image(order: Order) -> None:
    """Eski buyurtmalar: token bor, rasm yo‘q — qayta generatsiya."""
    if not order.cash_qr_token or order.payment_type != PaymentType.CASH.value:
        return
    if order.cash_qr_image:
        return
    from apps.orders.cash_qr import render_cash_qr_file

    png = render_cash_qr_file(order.cash_qr_token, filename=f'order_{order.pk}.png')
    order.cash_qr_image.save(f'order_{order.pk}.png', png, save=True)


def deduct_order_stock(order: Order) -> None:
    products_qs = OrderProduct.objects.select_related('product').filter(order=order)
    for op in products_qs:
        if not op.product:
            continue
        norm = op.normalized_quantity if op.normalized_quantity is not None else op.quantity
        needed = stock_units_required(op.product, norm)
        dec = int(needed.to_integral_value(rounding=ROUND_CEILING))
        Products.objects.filter(id=op.product_id).update(quantity=F('quantity') - dec)


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

    if order.payment_type != PaymentType.CASH.value:
        raise CashDeliveryError('Faqat cash buyurtmalar uchun.', code='payment_type')

    if order.payment_status == PaymentStatus.PAID.value:
        raise CashDeliveryError('Buyurtma allaqachon to‘langan.', code='already_paid')

    if order.status == OrderStatus.COMPLETED.value:
        raise CashDeliveryError('Buyurtma allaqachon yakunlangan.', code='already_completed')

    if order.status not in CASH_QR_CONFIRM_STATUSES:
        raise CashDeliveryError(
            'Avval kuryer statusni delivered qiladi, keyin QR skaner qilinadi.',
            code='status',
        )

    is_assigned = OrderCourier.objects.filter(order_id=order.pk, courier_id=courier_user.pk).exists()
    if not is_assigned:
        raise CashDeliveryError('Siz bu buyurtmaga biriktirilmagansiz.', code='courier')

    if not order.cash_qr_token or order.cash_qr_token != code:
        raise CashDeliveryError('QR code noto‘g‘ri yoki muddati tugagan.', code='qr_mismatch')

    now = timezone.now()
    if order.cash_qr_image:
        order.cash_qr_image.delete(save=False)
    order.cash_qr_token = None
    order.qr_confirmed_at = now
    if not order.delivered_at:
        order.delivered_at = now
    order.status = OrderStatus.COMPLETED.value
    order.payment_status = PaymentStatus.PAID.value
    mark_order_paid_amount(order)
    compute_order_settlement(order)
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

    payload = {
        'order_id': order.pk,
        'message': (
            'Курьер подтвердил оплату. Вы получили заказ? '
            'Подтвердите получение в приложении.'
        ),
        'payment_status': order.payment_status,
        'status': order.status,
        'delivered_at': order.delivered_at.isoformat(),
        'estimated_total': str(order.estimated_total),
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
    on_status_changed(order.pk, OrderStatus.COMPLETED.value, OrderStatus.DELIVERED.value)
    logger.info(
        'Cash QR confirmed order=%s courier=%s',
        order.pk,
        courier_user.pk,
    )

    summary = {
        'order_id': order.pk,
        'payment_status': order.payment_status,
        'status': order.status,
        'delivered_at': order.delivered_at.isoformat(),
    }
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

    if order.payment_type != PaymentType.CASH.value:
        raise CashDeliveryError('Faqat cash buyurtma.', code='payment_type')

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
