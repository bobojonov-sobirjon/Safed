from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db.models import QuerySet

from .models import DeliveryFeeRule, OrderFeeSettings, Order


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def get_fee_settings() -> OrderFeeSettings:
    obj, _ = OrderFeeSettings.objects.get_or_create(pk=1)
    return obj


def get_delivery_fee(subtotal: Decimal, rules: Optional[QuerySet[DeliveryFeeRule]] = None) -> Decimal:
    subtotal = _d(subtotal)
    rules_qs = rules if rules is not None else DeliveryFeeRule.objects.filter(is_active=True)
    rules_qs = rules_qs.order_by('min_order_amount', 'id')

    for r in rules_qs:
        if subtotal < r.min_order_amount:
            continue
        if r.max_order_amount is not None and subtotal > r.max_order_amount:
            continue
        return _d(r.fee_amount)
    return Decimal('0.00')


def compute_order_pricing(order: Order) -> Order:
    """
    Compute pricing fields on Order without touching payment.
    """
    settings = get_fee_settings()
    products_subtotal = _d(order.calculate_total())
    service_fee_percent = _d(settings.service_fee_percent)
    service_fee_amount = (products_subtotal * service_fee_percent / Decimal('100')).quantize(Decimal('0.01'))
    packing_fee = _d(settings.packing_fee_amount)
    delivery_fee = get_delivery_fee(products_subtotal)

    estimated_total = (products_subtotal + service_fee_amount + packing_fee + delivery_fee).quantize(Decimal('0.01'))

    order.products_subtotal = products_subtotal
    order.service_fee_percent = service_fee_percent
    order.service_fee_amount = service_fee_amount
    order.packing_fee = packing_fee
    order.delivery_fee = delivery_fee
    order.estimated_total = estimated_total
    return order

