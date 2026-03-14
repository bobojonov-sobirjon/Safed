"""
Order-related models.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Optional, List
from django.db import models
from django.utils import timezone

from apps.core.enums import OrderStatus


class Order(models.Model):
    """Customer order."""
    
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Пользователь',
    )
    lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name='Широта',
    )
    long = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name='Долгота',
    )
    address = models.TextField(
        verbose_name='Адрес',
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices(),
        default=OrderStatus.PENDING.value,
        verbose_name='Статус',
        db_index=True
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Общая сумма'
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name='Примечания'
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='Удалён',
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f'Order #{self.pk}'

    @property
    def can_update_or_delete(self) -> bool:
        """Check if order can be modified."""
        return self.status == OrderStatus.PENDING.value

    @property
    def can_add_courier(self) -> bool:
        """Check if courier can be assigned."""
        return self.status == OrderStatus.PROCESS.value
    
    @property
    def is_active(self) -> bool:
        """Check if order is in active status."""
        return self.status in OrderStatus.active_statuses()
    
    @property
    def is_completed(self) -> bool:
        """Check if order is completed."""
        return self.status == OrderStatus.COMPLETED.value
    
    def calculate_total(self) -> Decimal:
        """Calculate total amount from order products."""
        total = self.order_products.aggregate(
            total=models.Sum('total_price')
        )['total'] or Decimal('0.00')
        return total
    
    def update_total(self):
        """Update total_amount field."""
        self.total_amount = self.calculate_total()
        self.save(update_fields=['total_amount'])
    
    def can_transition_to(self, new_status: str) -> bool:
        """Check if status transition is valid."""
        valid_transitions = {
            OrderStatus.PENDING.value: [OrderStatus.PROCESS.value, OrderStatus.REJECTED.value],
            OrderStatus.PROCESS.value: [OrderStatus.DELIVERING.value, OrderStatus.REJECTED.value],
            OrderStatus.DELIVERING.value: [OrderStatus.COMPLETED.value, OrderStatus.REJECTED.value],
            OrderStatus.COMPLETED.value: [],
            OrderStatus.REJECTED.value: [],
        }
        return new_status in valid_transitions.get(self.status, [])


class OrderProduct(models.Model):
    """Product in an order."""
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='order_products',
        verbose_name='Заказ',
    )
    product = models.ForeignKey(
        'products.Products',
        on_delete=models.PROTECT,
        related_name='order_products',
        verbose_name='Продукт',
    )
    quantity = models.PositiveIntegerField(
        verbose_name='Количество'
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Цена за единицу',
        default=Decimal('0.00')
    )
    total_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Сумма',
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = 'Продукт заказа'
        verbose_name_plural = 'Продукты заказа'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['product']),
        ]

    def __str__(self) -> str:
        return f'OrderProduct #{self.pk}'
    
    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.current_price
        super().save(*args, **kwargs)


class OrderCourier(models.Model):
    """Courier assignment to order."""
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='order_couriers',
        verbose_name='Заказ',
    )
    courier = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        related_name='assigned_orders',
        verbose_name='Курьер',
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Завершён'
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name='Примечания'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = 'Курьер заказа'
        verbose_name_plural = 'Курьеры заказов'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['courier']),
        ]

    def __str__(self) -> str:
        return f'OrderCourier #{self.pk}'
