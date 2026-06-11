"""
Акт сверки с поставщиком.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone

from ..models import ReceiptStatus, StockReceipt, Supplier, SupplierReconciliationAct, ReconciliationActStatus


class ReconciliationError(Exception):
    def __init__(self, message: str, *, code: str = 'error'):
        self.message = message
        self.code = code
        super().__init__(message)


def posted_receipts_for_period(supplier_id: int, period_from, period_to):
    return StockReceipt.objects.filter(
        supplier_id=supplier_id,
        status=ReceiptStatus.POSTED,
        doc_date__gte=period_from,
        doc_date__lte=period_to,
    ).order_by('doc_date', 'id')


def build_reconciliation_preview(
    supplier: Supplier,
    *,
    period_from,
    period_to,
    opening_balance: Decimal,
) -> dict:
    qs = posted_receipts_for_period(supplier.pk, period_from, period_to)
    agg = qs.aggregate(
        total=Sum('subtotal'),
        count=Count('id'),
    )
    receipts_total = agg['total'] or Decimal('0.00')
    receipts_count = int(agg['count'] or 0)
    closing_balance = (opening_balance + receipts_total).quantize(Decimal('0.01'))
    return {
        'receipts_total': receipts_total,
        'receipts_count': receipts_count,
        'closing_balance': closing_balance,
        'receipts': list(qs),
    }


@transaction.atomic
def confirm_reconciliation_act(act: SupplierReconciliationAct, *, confirmed_by) -> SupplierReconciliationAct:
    act = SupplierReconciliationAct.objects.select_for_update().get(pk=act.pk)
    if act.status != ReconciliationActStatus.DRAFT:
        raise ReconciliationError('Акт уже подтверждён.', code='already_confirmed')
    if act.period_to < act.period_from:
        raise ReconciliationError('period_to не может быть раньше period_from.', code='invalid_period')

    preview = build_reconciliation_preview(
        act.supplier,
        period_from=act.period_from,
        period_to=act.period_to,
        opening_balance=act.opening_balance,
    )
    act.receipts_total = preview['receipts_total']
    act.receipts_count = preview['receipts_count']
    act.closing_balance = preview['closing_balance']
    act.status = ReconciliationActStatus.CONFIRMED
    act.confirmed_at = timezone.now()
    act.confirmed_by = confirmed_by
    act.save(
        update_fields=[
            'receipts_total',
            'receipts_count',
            'closing_balance',
            'status',
            'confirmed_at',
            'confirmed_by',
            'updated_at',
        ],
    )
    return act
