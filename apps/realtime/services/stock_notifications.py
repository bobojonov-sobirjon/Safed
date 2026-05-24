"""
Low-stock WebSocket notifications for Operator / Super Admin (Russian copy).
"""
from __future__ import annotations

import logging

from apps.core.enums import ProductUnit
from apps.products.models import Products
from apps.realtime.services.notify import notify_users
from apps.realtime.services.order_notifications import _staff_user_ids

logger = logging.getLogger(__name__)

STAFF_LOW_STOCK_TITLE = 'Низкий остаток'
STAFF_LOW_STOCK_BODY = (
    'Товар «{product_name}» заканчивается: на складе осталось {quantity}{unit_suffix}. '
    'Требуется пополнение.'
)

_UNIT_SUFFIX = {
    ProductUnit.PIECE.value: ' шт.',
    ProductUnit.KG.value: ' кг',
    ProductUnit.GRAM.value: ' г',
    ProductUnit.LITER.value: ' л',
    ProductUnit.ML.value: ' мл',
}


def _quantity_unit_suffix(product: Products) -> str:
    return _UNIT_SUFFIX.get(product.product_unit or ProductUnit.PIECE.value, '')


def notify_staff_low_stock(product_id: int) -> None:
    try:
        product = Products.objects.get(pk=product_id, is_deleted=False)
    except Products.DoesNotExist:
        return

    name = product.safe_translation_getter('name', any_language=True) or f'ID {product.pk}'
    body = STAFF_LOW_STOCK_BODY.format(
        product_name=name,
        quantity=product.quantity,
        unit_suffix=_quantity_unit_suffix(product),
    )
    notify_users(
        _staff_user_ids(),
        title=STAFF_LOW_STOCK_TITLE,
        body=body,
        notif_type='staff_low_stock',
        data={
            'event': 'staff_low_stock',
            'product_id': product.pk,
            'quantity': product.quantity,
            'product_unit': product.product_unit,
        },
        send_push=False,
    )
    logger.info('Staff WS low stock product=%s qty=%s', product.pk, product.quantity)
