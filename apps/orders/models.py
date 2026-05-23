"""
Order-related models.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Optional, List
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from parler.models import TranslatableModel, TranslatedFields

from apps.core.enums import OrderStatus, PaymentStatus, PaymentType


class OrderCancelReason(TranslatableModel):
    """Predefined reasons shown when the customer cancels an order."""

    code = models.SlugField(max_length=50, unique=True, verbose_name='Код')
    translations = TranslatedFields(
        name=models.CharField(max_length=255, verbose_name='Название'),
    )
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Причина отмены'
        verbose_name_plural = 'Причины отмены'
        ordering = ['sort_order', 'id']

    def __str__(self) -> str:
        return self.safe_translation_getter('name', default=self.code)


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
        default=OrderStatus.CREATED.value,
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
    original_estimated_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Сумма при оформлении',
    )
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Оплачено клиентом',
    )
    adjustment_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Разница после yig‘ish (+ доплата, − возврат)',
    )
    final_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Итог после yig‘ish',
    )
    refund_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сумма возврата',
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
    delivery_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата доставки',
        db_index=True,
    )
    delivery_time_start = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Начало интервала доставки',
    )
    delivery_time_end = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Конец интервала доставки',
    )
    delivery_slot = models.ForeignKey(
        'orders.DeliverySlot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Слот доставки',
    )
    delivery_address = models.ForeignKey(
        'orders.DeliveryAddress',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Адрес доставки',
    )
    payment_type = models.CharField(
        max_length=10,
        choices=PaymentType.choices(),
        default=PaymentType.CASH.value,
        verbose_name='Способ оплаты',
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices(),
        default=PaymentStatus.PENDING.value,
        verbose_name='Статус оплаты',
        db_index=True,
    )
    buffer_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Буфер по весу',
    )
    loyalty_points_used = models.PositiveIntegerField(
        default=0,
        verbose_name='Списано баллов',
    )
    loyalty_discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Скидка баллами',
    )
    leave_at_door = models.BooleanField(
        default=False,
        verbose_name='Оставить у двери',
    )
    cancel_comment = models.TextField(
        blank=True,
        default='',
        verbose_name='Комментарий при отмене',
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время отмены',
    )
    cancel_reasons = models.ManyToManyField(
        OrderCancelReason,
        related_name='orders',
        blank=True,
        verbose_name='Причины отмены',
    )
    cash_qr_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Cash QR token',
    )
    cash_qr_image = models.ImageField(
        upload_to='orders/cash_qr/',
        null=True,
        blank=True,
        verbose_name='Cash QR rasm (PNG)',
    )
    qr_confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='QR tasdiqlangan vaqt',
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Yetkazilgan vaqt',
    )
    customer_delivery_accepted = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Mijoz qabul qildi',
    )
    customer_delivery_responded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Mijoz javobi vaqti',
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
        """Cart / order lines editable only in created."""
        return self.status == OrderStatus.CREATED.value

    @property
    def can_user_cancel(self) -> bool:
        return self.status in OrderStatus.user_cancellable_statuses()

    @property
    def can_add_courier(self) -> bool:
        """Courier assigned while picking; then status becomes shipped."""
        return self.status == OrderStatus.PICKING.value
    
    @property
    def is_active(self) -> bool:
        """Check if order is in active status."""
        return self.status in OrderStatus.active_statuses()
    
    @property
    def is_completed(self) -> bool:
        """Cash va card: faqat QR tasdiqlangandan keyin completed."""
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
        """Staff / system status transitions."""
        valid_transitions = {
            OrderStatus.CREATED.value: [
                OrderStatus.CONFIRMED.value,
                OrderStatus.REJECTED.value,
                OrderStatus.CANCELLED.value,
            ],
            OrderStatus.CONFIRMED.value: [
                OrderStatus.PICKING.value,
                OrderStatus.REJECTED.value,
                OrderStatus.CANCELLED.value,
            ],
            OrderStatus.PICKING.value: [
                OrderStatus.SHIPPED.value,
                OrderStatus.REJECTED.value,
                OrderStatus.CANCELLED.value,
            ],
            OrderStatus.SHIPPED.value: [
                OrderStatus.DELIVERED.value,
                OrderStatus.REJECTED.value,
            ],
            OrderStatus.DELIVERED.value: [],
            OrderStatus.COMPLETED.value: [],
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
    ordered_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Заказано при оформлении',
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name='Количество',
        help_text='Miqdor (product_unit bo‘yicha).',
    )
    product_unit = models.CharField(
        max_length=16,
        default='piece',
        verbose_name='Единица строки',
        help_text='Mijoz yuborgan yoki katalog birligi.',
    )
    normalized_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Нормализованное кол-во',
        help_text='Katalog product_unit bo‘yicha (narx hisobi uchun).',
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
    min_order_subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('1000.00'),
        verbose_name='Мин. сумма товаров для оформления',
    )
    weight_buffer_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        verbose_name='Буфер по весу, %',
    )
    loyalty_point_currency_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('1.0000'),
        verbose_name='Сумма за 1 балл (UZS)',
    )
    hourly_delivery_capacity = models.PositiveIntegerField(
        default=15,
        verbose_name='Макс. заказов на один часовой интервал доставки',
        help_text='Для сетки GET /busy-slots/?date= и legacy delivery_date/time.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Настройки сборов'
        verbose_name_plural = 'Настройки сборов'

    def __str__(self) -> str:
        return f'Settings #{self.pk}'


class DeliveryAddress(models.Model):
    """Structured delivery address per user (Korzinka-style)."""
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='delivery_addresses',
        verbose_name='Пользователь',
    )
    label = models.CharField(max_length=100, blank=True, default='', verbose_name='Подпись')
    street = models.CharField(max_length=255, verbose_name='Улица / район')
    house_number = models.CharField(max_length=50, blank=True, default='', verbose_name='Дом')
    apartment = models.CharField(max_length=50, blank=True, default='', verbose_name='Квартира')
    entrance = models.CharField(max_length=50, blank=True, default='', verbose_name='Подъезд')
    floor = models.CharField(max_length=20, blank=True, default='', verbose_name='Этаж')
    intercom_code = models.CharField(max_length=50, blank=True, default='', verbose_name='Домофон')
    lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Широта')
    long = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Долгота')
    is_default = models.BooleanField(default=False, db_index=True, verbose_name='По умолчанию')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Адрес доставки'
        verbose_name_plural = 'Адреса доставки'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self) -> str:
        return f'{self.street} {self.house_number}'.strip() or f'Address #{self.pk}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            DeliveryAddress.objects.filter(user_id=self.user_id).exclude(pk=self.pk).update(is_default=False)


class DeliverySlot(models.Model):
    """Bookable delivery window with capacity."""
    slot_date = models.DateField(verbose_name='Дата', db_index=True)
    start_time = models.TimeField(verbose_name='Начало')
    end_time = models.TimeField(verbose_name='Конец')
    capacity = models.PositiveIntegerField(default=30, verbose_name='Макс. заказов')
    delivery_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Доставка в слоте',
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Слот доставки'
        verbose_name_plural = 'Слоты доставки'
        ordering = ['slot_date', 'start_time', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['slot_date', 'start_time', 'end_time'],
                name='uniq_delivery_slot_window',
            ),
        ]
        indexes = [
            models.Index(fields=['slot_date', 'is_active']),
        ]

    def __str__(self) -> str:
        return f'{self.slot_date} {self.start_time}-{self.end_time}'


class BusyDayWorkingHours(models.Model):
    """Per-day delivery window: hourly grid and order validation use these times."""
    date = models.DateField(verbose_name='Дата', unique=True, db_index=True)
    working_start = models.TimeField(verbose_name='Начало рабочего дня')
    working_end = models.TimeField(verbose_name='Конец рабочего дня')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Рабочие часы дня (доставка)'
        verbose_name_plural = 'Рабочие часы по дням'
        ordering = ['-date', 'id']

    def clean(self) -> None:
        if self.working_end <= self.working_start:
            raise ValidationError({'working_end': 'Должно быть позже working_start.'})

    def __str__(self) -> str:
        return f'{self.date} {self.working_start}-{self.working_end}'


class BusySlot(models.Model):
    """Blocked delivery interval for a calendar day (admin)."""
    date = models.DateField(verbose_name='Дата', db_index=True)
    start_time = models.TimeField(verbose_name='Начало')
    end_time = models.TimeField(verbose_name='Конец')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Занятый слот'
        verbose_name_plural = 'Занятые слоты'
        ordering = ['date', 'start_time', 'id']
        indexes = [
            models.Index(fields=['date']),
        ]

    def clean(self) -> None:
        if self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'Должно быть позже start_time.'})

    def __str__(self) -> str:
        return f'BusySlot #{self.pk} {self.date} {self.start_time}-{self.end_time}'


class ClickPayment(models.Model):
    """CLICK Prepare/Complete transaction linked to an order."""

    class State(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PREPARED = 'prepared', 'Prepared'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='click_payments',
        verbose_name='Заказ',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Сумма')
    click_trans_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='CLICK trans id',
    )
    click_paydoc_id = models.BigIntegerField(null=True, blank=True, verbose_name='CLICK paydoc id')
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.PENDING,
        db_index=True,
    )
    last_error_code = models.IntegerField(null=True, blank=True)
    last_error_note = models.CharField(max_length=255, blank=True, default='')
    prepared_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'CLICK платёж'
        verbose_name_plural = 'CLICK платежи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'ClickPayment #{self.pk} order={self.order_id} {self.state}'
