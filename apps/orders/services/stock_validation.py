from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

from apps.core.enums import ProductUnit
from apps.products.models import Products
from apps.products.unit_pricing import catalog_unit_for_product, stock_units_required

INSUFFICIENT_STOCK_DETAIL = "Ba'zi mahsulotlar omborda yetarli emas"

_UNIT_LABEL_UZ = {
    ProductUnit.PIECE.value: 'dona',
    ProductUnit.KG.value: 'kg',
    ProductUnit.GRAM.value: 'g',
    ProductUnit.LITER.value: 'litr',
    ProductUnit.ML.value: 'ml',
}


def _unit_label_uz(product: Products) -> str:
    return _UNIT_LABEL_UZ.get(product.product_unit or ProductUnit.PIECE.value, 'dona')


def _qty_display(value, *, as_piece: bool) -> str:
    if as_piece:
        return str(int(value))
    if isinstance(value, Decimal):
        text = format(value.normalize(), 'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    return str(value)


def build_stock_shortage_message(
    product: Products,
    *,
    available,
    requested,
) -> str:
    unit = _unit_label_uz(product)
    as_piece = catalog_unit_for_product(product) == ProductUnit.PIECE.value
    avail_s = _qty_display(available, as_piece=as_piece)
    req_s = _qty_display(requested, as_piece=as_piece)
    return f"Omborda faqat {avail_s} {unit} bor, siz {req_s} {unit} so'radingiz"


def collect_insufficient_stock(
    products_by_id: Mapping[int, Products],
    products_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return per-product shortage info when warehouse stock is not enough."""
    insufficient: List[Dict[str, Any]] = []
    for item in products_data:
        product = products_by_id.get(item['product_id'])
        if not product:
            continue
        needed = stock_units_required(product, item['normalized_quantity'])
        catalog = catalog_unit_for_product(product)
        if catalog == ProductUnit.PIECE.value:
            available = int(product.quantity or 0)
            requested = int(needed.to_integral_value())
            if available < requested:
                insufficient.append({
                    'product_id': product.id,
                    'available_quantity': available,
                    'requested_quantity': str(requested),
                    'message': build_stock_shortage_message(
                        product,
                        available=available,
                        requested=requested,
                    ),
                })
        elif Decimal(product.quantity or 0) < needed:
            available = product.quantity
            insufficient.append({
                'product_id': product.id,
                'available_quantity': str(available),
                'requested_quantity': str(needed),
                'message': build_stock_shortage_message(
                    product,
                    available=available,
                    requested=needed,
                ),
            })
    return insufficient


def insufficient_stock_response(insufficient: List[Dict[str, Any]]):
    from rest_framework import status
    from rest_framework.response import Response

    return Response(
        {
            'detail': INSUFFICIENT_STOCK_DETAIL,
            'products': insufficient,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
