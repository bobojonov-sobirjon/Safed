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


class StockReceipt(models.Model):
    """Приходный документ."""
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='receipts')
    doc_number = models.CharField(max_length=50, db_index=True)
    doc_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=ReceiptStatus.choices, default=ReceiptStatus.DRAFT, db_index=True)

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey('accounts.CustomUser', on_delete=models.PROTECT, null=True, blank=True, related_name='created_receipts')
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

