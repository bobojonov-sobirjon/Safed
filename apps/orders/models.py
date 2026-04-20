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
    entrance = models.CharField(
        max_length=50,
        verbose_name='Подъезд',
        null=True,
        blank=True,
    )
    apartment = models.CharField(
        max_length=50,
        verbose_name='Дом/квартира',
        null=True,
        blank=True,
    )
    comment = models.TextField(
        verbose_name='Комментарий',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices(),
        default=OrderStatus.NEW.value,
        verbose_name='Статус',
        db_index=True
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Общая сумма'
    )
    # Pricing snapshots (admin pricing + fees)
    products_subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сумма товаров'
    )
    service_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сервисный процент'
    )
    service_fee_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сервисный сбор'
    )
    delivery_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Доставка'
    )
    packing_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Пакет/сбор'
    )
    estimated_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Оценочная сумма'
    )
    final_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Итоговая сумма (admin)'
    )
    refund_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сумма возврата'
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
        return self.status == OrderStatus.NEW.value

    @property
    def can_add_courier(self) -> bool:
        """Check if courier can be assigned."""
        return self.status == OrderStatus.PICKING.value
    
    @property
    def is_active(self) -> bool:
        """Check if order is in active status."""
        return self.status in OrderStatus.active_statuses()
    
    @property
    def is_completed(self) -> bool:
        """Check if order is completed."""
        return self.status == OrderStatus.DELIVERED.value
    
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
            OrderStatus.NEW.value: [OrderStatus.PICKING.value, OrderStatus.REJECTED.value, OrderStatus.CANCELLED.value],
            OrderStatus.PICKING.value: [OrderStatus.ON_THE_WAY.value, OrderStatus.REJECTED.value, OrderStatus.CANCELLED.value],
            OrderStatus.ON_THE_WAY.value: [OrderStatus.DELIVERED.value, OrderStatus.REJECTED.value],
            OrderStatus.DELIVERED.value: [],
            OrderStatus.REJECTED.value: [],
            OrderStatus.CANCELLED.value: [],
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


class DeliveryFeeRule(models.Model):
    """Delivery fee rules by order subtotal thresholds."""
    min_order_amount = models.DecimalField(max_digits=14, decimal_places=2)
    max_order_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    fee_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Правило доставки'
        verbose_name_plural = 'Правила доставки'
        ordering = ['min_order_amount', 'id']
        indexes = [models.Index(fields=['is_active', 'min_order_amount'])]

    def __str__(self) -> str:
        max_part = f'..{self.max_order_amount}' if self.max_order_amount is not None else '..+inf'
        return f'{self.min_order_amount}{max_part} => {self.fee_amount}'


class OrderFeeSettings(models.Model):
    """Singleton settings for order fees."""
    service_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    packing_fee_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Настройки сборов'
        verbose_name_plural = 'Настройки сборов'

    def __str__(self) -> str:
        return f'Settings #{self.pk}'
