from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from django.db.models import QuerySet

from apps.core.enums import OrderStatus
from apps.products.unit_pricing import product_applies_weight_buffer

from .models import DeliveryFeeRule, OrderFeeSettings, Order

if TYPE_CHECKING:
    from apps.accounts.models import CustomUser


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def get_fee_settings() -> OrderFeeSettings:
    obj, _ = OrderFeeSettings.objects.get_or_create(pk=1)
    return obj


def get_delivery_fee_from_rules(subtotal: Decimal, rules: Optional[QuerySet[DeliveryFeeRule]] = None) -> Decimal:
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


def order_products_buffer_sum(order: Order, weight_buffer_percent: Decimal) -> Decimal:
    """Buffer only on weight-based lines (percent of line total_price)."""
    pct = _d(weight_buffer_percent)
    total_buf = Decimal('0.00')
    for op in order.order_products.select_related('product'):
        if not op.product:
            continue
        if not product_applies_weight_buffer(op.product):
            continue
        line = _d(op.total_price)
        total_buf += (line * pct / Decimal('100')).quantize(Decimal('0.01'))
    return total_buf.quantize(Decimal('0.01'))


def loyalty_discount_cap(base_before_loyalty: Decimal) -> Decimal:
    return (base_before_loyalty * Decimal('0.5')).quantize(Decimal('0.01'))


def compute_loyalty_discount_amount(
    *,
    points_to_use: int,
    user_balance_points: int,
    point_value: Decimal,
    base_before_loyalty: Decimal,
) -> Tuple[int, Decimal]:
    """
    Returns (points_applied, money_discount).
    Rule: discount from points cannot exceed 50% of base_before_loyalty.
    """
    if points_to_use <= 0:
        return 0, Decimal('0.00')
    pv = _d(point_value)
    if pv <= 0:
        return 0, Decimal('0.00')
    max_money = loyalty_discount_cap(base_before_loyalty)
    max_points = int((max_money / pv).to_integral_value(rounding='ROUND_DOWN'))
    pts = min(points_to_use, user_balance_points, max_points)
    money = (Decimal(pts) * pv).quantize(Decimal('0.01'))
    return pts, money


def compute_order_pricing(order: Order) -> Order:
    """
    Recompute pricing snapshots on Order (products_subtotal, fees, buffer, loyalty, estimated_total).
    Expects order_products already saved; loyalty_points_used is authoritative for discount amount
    (capped by 50% of base — validate at checkout before deducting user points).
    """
    settings = get_fee_settings()
    products_subtotal = _d(order.calculate_total())
    weight_buffer_percent = _d(settings.weight_buffer_percent)
    buffer_amount = order_products_buffer_sum(order, weight_buffer_percent)

    service_fee_percent = _d(settings.service_fee_percent)
    service_fee_amount = (products_subtotal * service_fee_percent / Decimal('100')).quantize(Decimal('0.01'))
    packing_fee = _d(settings.packing_fee_amount)

    if order.delivery_slot_id and order.delivery_slot:
        delivery_fee = _d(order.delivery_slot.delivery_fee)
    else:
        delivery_fee = get_delivery_fee_from_rules(products_subtotal)

    base_before_loyalty = (
        products_subtotal + buffer_amount + service_fee_amount + packing_fee + delivery_fee
    ).quantize(Decimal('0.01'))

    point_value = _d(settings.loyalty_point_currency_value)
    pts_used = int(order.loyalty_points_used or 0)
    max_money = loyalty_discount_cap(base_before_loyalty)
    if point_value > 0 and pts_used > 0:
        discount = min(Decimal(pts_used) * point_value, max_money).quantize(Decimal('0.01'))
    else:
        discount = Decimal('0.00')
    order.loyalty_discount_amount = discount

    estimated_total = (base_before_loyalty - discount).quantize(Decimal('0.01'))
    if estimated_total < 0:
        estimated_total = Decimal('0.00')

    order.products_subtotal = products_subtotal
    order.buffer_amount = buffer_amount
    order.service_fee_percent = service_fee_percent
    order.service_fee_amount = service_fee_amount
    order.packing_fee = packing_fee
    order.delivery_fee = delivery_fee
    order.estimated_total = estimated_total
    order.total_amount = products_subtotal
    return order


def snapshot_order_checkout_total(order: Order) -> None:
    if order.original_estimated_total is None:
        order.original_estimated_total = _d(order.estimated_total).quantize(Decimal('0.01'))


def mark_order_paid_amount(order: Order) -> None:
    order.paid_amount = _d(order.estimated_total).quantize(Decimal('0.01'))


def settlement_baseline_amount(order: Order) -> Decimal:
    """
    Sum already committed by the customer (or quoted at checkout).
    - card: paid_amount after CLICK (or original if not paid yet)
    - cash: original_estimated_total until delivery payment is recorded
    """
    if order.paid_amount is not None:
        return _d(order.paid_amount).quantize(Decimal('0.01'))
    if order.original_estimated_total is not None:
        return _d(order.original_estimated_total).quantize(Decimal('0.01'))
    return _d(order.estimated_total).quantize(Decimal('0.01'))


def compute_order_settlement(order: Order) -> Order:
    new_total = _d(order.estimated_total).quantize(Decimal('0.01'))
    order.final_total = new_total
    baseline = settlement_baseline_amount(order)
    delta = (new_total - baseline).quantize(Decimal('0.01'))
    order.adjustment_balance = delta
    order.refund_amount = abs(delta) if delta < 0 else Decimal('0.00')
    return order


def settlement_type_for(order: Order) -> str:
    delta = _d(order.adjustment_balance)
    if delta > 0:
        return 'extra_payment'
    if delta < 0:
        return 'refund'
    return 'none'


def min_order_check(products_subtotal: Decimal) -> Tuple[bool, Decimal, Decimal]:
    """Returns (ok, threshold, shortfall). shortfall 0 if ok."""
    settings = get_fee_settings()
    threshold = _d(settings.min_order_subtotal)
    sub = _d(products_subtotal)
    if sub >= threshold:
        return True, threshold, Decimal('0.00')
    return False, threshold, (threshold - sub).quantize(Decimal('0.01'))


def build_pricing_preview(
    *,
    products_data: List[Dict[str, Any]],
    products_by_id: Dict[int, Any],
    delivery_slot: Optional[Any],
    loyalty_points_to_use: int,
    user: Optional['CustomUser'] = None,
) -> Dict[str, Any]:
    """
    Pure pricing preview for cart (no order). products_data: product_id, quantity (decimal), total_price.
    """
    settings = get_fee_settings()
    lines_subtotal = Decimal('0.00')
    weight_buffer_percent = _d(settings.weight_buffer_percent)
    buffer_amount = Decimal('0.00')

    for item in products_data:
        pid = item['product_id']
        p = products_by_id.get(pid)
        qty = _d(item.get('quantity'))
        line_total = _d(item.get('total_price'))
        lines_subtotal += line_total
        if p and product_applies_weight_buffer(p):
            buffer_amount += (line_total * weight_buffer_percent / Decimal('100')).quantize(Decimal('0.01'))
    buffer_amount = buffer_amount.quantize(Decimal('0.01'))

    service_fee_amount = (lines_subtotal * _d(settings.service_fee_percent) / Decimal('100')).quantize(Decimal('0.01'))
    packing_fee = _d(settings.packing_fee_amount)
    if delivery_slot is not None:
        delivery_fee = _d(delivery_slot.delivery_fee)
    else:
        delivery_fee = get_delivery_fee_from_rules(lines_subtotal)

    base_before_loyalty = (
        lines_subtotal + buffer_amount + service_fee_amount + packing_fee + delivery_fee
    ).quantize(Decimal('0.01'))

    pts_applied, discount = (0, Decimal('0.00'))
    if user is not None and loyalty_points_to_use > 0:
        pts_applied, discount = compute_loyalty_discount_amount(
            points_to_use=loyalty_points_to_use,
            user_balance_points=int(getattr(user, 'loyalty_points', 0) or 0),
            point_value=_d(settings.loyalty_point_currency_value),
            base_before_loyalty=base_before_loyalty,
        )

    estimated_total = (base_before_loyalty - discount).quantize(Decimal('0.01'))
    if estimated_total < 0:
        estimated_total = Decimal('0.00')

    ok, threshold, shortfall = min_order_check(lines_subtotal)

    return {
        'products_subtotal': str(lines_subtotal),
        'buffer_amount': str(buffer_amount),
        'service_fee_amount': str(service_fee_amount),
        'packing_fee': str(packing_fee),
        'delivery_fee': str(delivery_fee),
        'base_before_loyalty': str(base_before_loyalty),
        'loyalty_points_applied': pts_applied,
        'loyalty_discount_amount': str(discount),
        'estimated_total': str(estimated_total),
        'min_order_subtotal': str(threshold),
        'min_order_met': ok,
        'amount_to_min_order': str(shortfall),
        'can_checkout': ok,
        'loyalty_max_money': str(loyalty_discount_cap(base_before_loyalty)),
    }
