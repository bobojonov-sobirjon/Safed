"""Picking: actual qty/weight → repricing → settlement (refund / extra payment)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.db import transaction

from apps.core.enums import OrderStatus, ProductUnit
from apps.products.unit_pricing import (
    UnitPricingError,
    catalog_unit_for_product,
    convert_quantity,
    line_total_from_normalized,
    unit_amount_for_product,
    validate_quantity_for_unit,
)
from apps.orders.models import Order, OrderProduct
from apps.orders.pricing import (
    compute_order_pricing,
    compute_order_settlement,
    snapshot_order_checkout_total,
)
from apps.products.models import ProductBarcode, Products

PICKING_ALLOWED_STATUSES = (OrderStatus.CONFIRMED.value, OrderStatus.PICKING.value)


class PickingError(Exception):
    def __init__(self, message: str, *, code: str = 'invalid'):
        self.message = message
        self.code = code
        super().__init__(message)


def validate_quantity_for_product(product: Products, qty: Decimal, *, product_unit: str) -> None:
    try:
        validate_quantity_for_unit(qty, product_unit, product_id=product.pk)
    except UnitPricingError as exc:
        raise PickingError(exc.message, code=exc.code) from exc


def default_picking_input_unit(order_product: OrderProduct, product: Products) -> str:
    """
  Picking quantity defaults to the unit the customer used at checkout (usually piece),
  not the catalog storage unit (gram/ml per pack).
    """
    catalog = catalog_unit_for_product(product)
    line_unit = order_product.product_unit or catalog
    if line_unit == ProductUnit.PIECE.value:
        return ProductUnit.PIECE.value

    ua = unit_amount_for_product(product)
    norm = Decimal(str(order_product.normalized_quantity or 0))
    qty = Decimal(str(order_product.quantity or 0))
    if catalog in (ProductUnit.GRAM.value, ProductUnit.ML.value) and ua > 1 and norm > 0:
        packs = (norm / ua).quantize(Decimal('0.001'))
        if packs == packs.to_integral_value() and (qty == packs or (qty == Decimal('1') and norm == ua)):
            return ProductUnit.PIECE.value

    if order_product.ordered_quantity is not None:
        oq = Decimal(str(order_product.ordered_quantity))
        if oq == oq.to_integral_value() and line_unit == ProductUnit.PIECE.value:
            return ProductUnit.PIECE.value

    return line_unit


@transaction.atomic
def apply_picking_quantity(
    *,
    order: Order,
    order_product: OrderProduct,
    quantity: Decimal,
    product_unit: Optional[str] = None,
) -> Tuple[Order, OrderProduct, Dict[str, Any]]:
    if order.is_deleted:
        raise PickingError('Заказ не найден.', code='not_found')
    if order.status not in PICKING_ALLOWED_STATUSES:
        raise PickingError('Доступно только для confirmed / picking.', code='status')

    order = Order.objects.select_for_update().get(pk=order.pk)
    order_product = (
        OrderProduct.objects.select_for_update()
        .select_related('product')
        .get(pk=order_product.pk, order_id=order.pk)
    )
    product = order_product.product
    if not product:
        raise PickingError('Продукт не найден.', code='product')

    catalog = catalog_unit_for_product(product)
    ua = unit_amount_for_product(product)
    request_unit = product_unit or default_picking_input_unit(order_product, product)
    qty = Decimal(str(quantity)).quantize(Decimal('0.001'))
    validate_quantity_for_product(product, qty, product_unit=request_unit)

    if order_product.ordered_quantity is None:
        order_product.ordered_quantity = order_product.quantity
    ordered_qty = Decimal(str(order_product.ordered_quantity)).quantize(Decimal('0.001'))

    unit_price = Decimal(str(order_product.unit_price)).quantize(Decimal('0.01'))
    old_norm = Decimal(str(order_product.normalized_quantity or order_product.quantity))
    old_line_total = line_total_from_normalized(
        unit_price=unit_price,
        normalized_quantity=old_norm,
        unit_amount=ua,
    )
    normalized = convert_quantity(qty, request_unit, catalog, unit_amount=ua)
    order_product.quantity = qty
    order_product.product_unit = request_unit
    order_product.normalized_quantity = normalized
    order_product.total_price = line_total_from_normalized(
        unit_price=unit_price,
        normalized_quantity=normalized,
        unit_amount=ua,
    )
    order_product.save(
        update_fields=[
            'ordered_quantity', 'quantity', 'product_unit',
            'normalized_quantity', 'total_price',
        ],
    )

    if order.status == OrderStatus.CONFIRMED.value:
        order.status = OrderStatus.PICKING.value

    compute_order_pricing(order)
    snapshot_order_checkout_total(order)
    compute_order_settlement(order)
    order.save()

    summary = {
        'order_product_id': order_product.pk,
        'product_id': product.pk,
        'ordered_quantity': str(ordered_qty),
        'actual_quantity': str(qty),
        'product_unit': request_unit,
        'normalized_quantity': str(normalized),
        'unit_price': str(unit_price),
        'line_total': str(order_product.total_price),
        'line_delta': str((order_product.total_price - old_line_total).quantize(Decimal('0.01'))),
    }
    return order, order_product, summary


@transaction.atomic
def apply_picking_by_barcode(
    *,
    order: Order,
    barcode: str,
    quantity: Optional[Decimal] = None,
    product_unit: Optional[str] = None,
) -> Tuple[Order, OrderProduct, Dict[str, Any]]:
    code = (barcode or '').strip()
    if not code:
        raise PickingError('Укажите barcode.', code='barcode')

    pb = ProductBarcode.objects.filter(barcode=code, is_active=True).select_related('product').first()
    if not pb or not pb.product:
        raise PickingError('Штрихкод не найден.', code='barcode')

    order_product = (
        OrderProduct.objects.filter(order_id=order.pk, product_id=pb.product_id)
        .select_related('product')
        .first()
    )
    if not order_product:
        raise PickingError('Этот товар не в заказе.', code='not_in_order')

    qty = order_product.quantity if quantity is None else Decimal(str(quantity)).quantize(Decimal('0.001'))
    return apply_picking_quantity(
        order=order,
        order_product=order_product,
        quantity=qty,
        product_unit=product_unit,
    )
