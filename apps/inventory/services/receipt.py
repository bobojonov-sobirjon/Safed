"""
Приход: проведение, отмена, пересчёт суммы.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.products.models import Products

from ..models import ReceiptStatus, StockReceipt, StockReceiptItem
from .stock import adjust_product_stock


class ReceiptError(Exception):
    def __init__(self, message: str, *, code: str = 'error'):
        self.message = message
        self.code = code
        super().__init__(message)


def recalculate_receipt_subtotal(receipt: StockReceipt) -> Decimal:
    total = receipt.items.aggregate(sum=Sum('line_total')).get('sum') or Decimal('0.00')
    receipt.subtotal = total
    receipt.save(update_fields=['subtotal', 'updated_at'])
    return total


@transaction.atomic
def post_stock_receipt(receipt: StockReceipt, *, posted_by) -> StockReceipt:
    receipt = StockReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status != ReceiptStatus.DRAFT:
        raise ReceiptError('Проведение возможно только из статуса черновик (draft).', code='invalid_status')

    items = list(receipt.items.select_related('product'))
    if not items:
        raise ReceiptError('Документ пустой.', code='empty')

    for item in items:
        if not item.product or item.product.is_deleted:
            raise ReceiptError(f'Товар строки #{item.pk} недоступен.', code='invalid_product')
        adjust_product_stock(item.product_id, int(item.quantity))
        if item.sell_price and item.sell_price > 0:
            Products.objects.filter(pk=item.product_id).update(price=item.sell_price)

    now = timezone.now()
    receipt.status = ReceiptStatus.POSTED
    receipt.posted_at = now
    receipt.posted_by = posted_by
    receipt.save(update_fields=['status', 'posted_at', 'posted_by', 'updated_at'])
    return receipt


@transaction.atomic
def cancel_stock_receipt(receipt: StockReceipt, *, cancelled_by) -> StockReceipt:
    receipt = StockReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status == ReceiptStatus.CANCELLED:
        raise ReceiptError('Документ уже отменён.', code='already_cancelled')
    if receipt.status == ReceiptStatus.POSTED:
        for item in receipt.items.select_related('product'):
            adjust_product_stock(item.product_id, -int(item.quantity))

    now = timezone.now()
    receipt.status = ReceiptStatus.CANCELLED
    receipt.cancelled_at = now
    receipt.cancelled_by = cancelled_by
    receipt.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'updated_at'])
    return receipt
