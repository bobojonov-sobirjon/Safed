from __future__ import annotations

from decimal import Decimal
from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=50, blank=True, default='')
    contact_person = models.CharField(max_length=255, blank=True, default='')
    inn = models.CharField(max_length=50, blank=True, default='')
    address = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.name


class ReceiptStatus(models.TextChoices):
    DRAFT = 'draft', 'Черновик'
    POSTED = 'posted', 'Проведен'
    CANCELLED = 'cancelled', 'Отменен'


class ReconciliationActStatus(models.TextChoices):
    DRAFT = 'draft', 'Черновик'
    CONFIRMED = 'confirmed', 'Подтверждён'


class StockReceipt(models.Model):
    """Приходный документ."""
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='receipts')
    doc_number = models.CharField(max_length=50, db_index=True)
    doc_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=ReceiptStatus.choices, default=ReceiptStatus.DRAFT, db_index=True)

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='created_receipts',
    )
    posted_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='posted_receipts',
    )
    posted_at = models.DateTimeField(null=True, blank=True, verbose_name='Проведён')
    cancelled_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cancelled_receipts',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Отменён')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Приход'
        verbose_name_plural = 'Приходы'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['supplier', 'doc_date']), models.Index(fields=['status'])]
        unique_together = [('doc_number',)]

    def __str__(self) -> str:
        return f'Receipt {self.doc_number}'


class StockReceiptItem(models.Model):
    receipt = models.ForeignKey(StockReceipt, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Products', on_delete=models.PROTECT, related_name='receipt_items')

    quantity = models.PositiveIntegerField()
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    sell_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    margin_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Snapshots for history (keep even if product soft-deleted/renamed)
    product_name_snapshot = models.CharField(max_length=255, blank=True, default='')
    barcode_snapshot = models.CharField(max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Товар прихода'
        verbose_name_plural = 'Товары прихода'
        ordering = ['id']
        indexes = [models.Index(fields=['receipt']), models.Index(fields=['product'])]

    def __str__(self) -> str:
        return f'Item #{self.pk} ({self.product_id})'


class SupplierReconciliationAct(models.Model):
    """Акт сверки с поставщиком за период."""

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='reconciliation_acts')
    period_from = models.DateField(db_index=True, verbose_name='Период с')
    period_to = models.DateField(db_index=True, verbose_name='Период по')
    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Начальный остаток (долг)',
    )
    receipts_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сумма приходов за период',
    )
    receipts_count = models.PositiveIntegerField(default=0, verbose_name='Кол-во приходов')
    closing_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Конечный остаток',
    )
    status = models.CharField(
        max_length=20,
        choices=ReconciliationActStatus.choices,
        default=ReconciliationActStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='created_reconciliation_acts',
    )
    confirmed_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='confirmed_reconciliation_acts',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Акт сверки'
        verbose_name_plural = 'Акты сверки'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['supplier', 'period_from', 'period_to']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'Акт #{self.pk} {self.supplier_id} {self.period_from}..{self.period_to}'

