from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import F

from apps.products.models import Products, ProductBarcode


class StockError(Exception):
    def __init__(self, message: str, *, code: str = 'error'):
        self.message = message
        self.code = code
        super().__init__(message)


def low_stock_threshold() -> int:
    return int(getattr(settings, 'LOW_STOCK_THRESHOLD', 5))


def _maybe_notify_low_stock(product_id: int, previous_quantity: int, new_quantity: int) -> None:
    threshold = low_stock_threshold()
    if previous_quantity > threshold >= new_quantity:
        from apps.realtime.services.stock_notifications import notify_staff_low_stock

        notify_staff_low_stock(product_id)


@transaction.atomic
def adjust_product_stock(product_id: int, delta: int) -> Products:
    """Change warehouse quantity; notify staff when stock crosses into low zone."""
    product = Products.objects.select_for_update().get(pk=product_id, is_deleted=False)
    previous_quantity = int(product.quantity or 0)
    Products.objects.filter(pk=product_id).update(quantity=F('quantity') + delta)
    product.refresh_from_db()
    _maybe_notify_low_stock(product_id, previous_quantity, int(product.quantity or 0))
    return product


@transaction.atomic
def restock_product_by_barcode(barcode: str, quantity: int) -> Products:
    code = (barcode or '').strip()
    if not code:
        raise StockError('Укажите штрихкод.', code='barcode')

    pb = (
        ProductBarcode.objects.filter(barcode=code, is_deleted=False)
        .select_related('product')
        .first()
    )
    if not pb or not pb.product or pb.product.is_deleted:
        raise StockError('Товар не найден', code='not_found')

    return adjust_product_stock(pb.product_id, quantity)
