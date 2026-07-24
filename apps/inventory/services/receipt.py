"""
Приход: проведение, отмена проводки, отмена документа, пересчёт суммы, автономер.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.products.models import Products

from ..models import ReceiptStatus, StockReceipt
from .stock import adjust_product_stock


class ReceiptError(Exception):
    def __init__(self, message: str, *, code: str = 'error'):
        self.message = message
        self.code = code
        super().__init__(message)


def next_receipt_doc_number() -> str:
    """Следующий код документа: 1, 2, 3... (как в UI «Код»)."""
    nums = []
    for n in StockReceipt.objects.values_list('doc_number', flat=True):
        if str(n).isdigit():
            nums.append(int(n))
    return str(max(nums) + 1) if nums else '1'


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
        if item.update_catalog_price and item.sell_price and item.sell_price > 0:
            Products.objects.filter(pk=item.product_id).update(price=item.sell_price)

    now = timezone.now()
    receipt.status = ReceiptStatus.POSTED
    receipt.posted_at = now
    receipt.posted_by = posted_by
    receipt.save(update_fields=['status', 'posted_at', 'posted_by', 'updated_at'])
    return receipt


@transaction.atomic
def unpost_stock_receipt(receipt: StockReceipt, *, unposted_by=None) -> StockReceipt:
    """Отменить проводку: posted → draft, остатки откатить."""
    receipt = StockReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status != ReceiptStatus.POSTED:
        raise ReceiptError('Отмена проводки возможна только для проведённого документа.', code='invalid_status')

    for item in receipt.items.select_related('product'):
        adjust_product_stock(item.product_id, -int(item.quantity))

    receipt.status = ReceiptStatus.DRAFT
    receipt.posted_at = None
    receipt.posted_by = None
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


@transaction.atomic
def set_receipt_paid_amount(receipt: StockReceipt, paid_amount: Decimal) -> StockReceipt:
    receipt = StockReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status == ReceiptStatus.CANCELLED:
        raise ReceiptError('Нельзя оплатить отменённый документ.', code='invalid_status')
    if paid_amount < 0:
        raise ReceiptError('Сумма оплаты не может быть отрицательной.', code='invalid_amount')
    receipt.paid_amount = paid_amount.quantize(Decimal('0.01'))
    receipt.save(update_fields=['paid_amount', 'updated_at'])
    return receipt
