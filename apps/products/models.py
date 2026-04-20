"""
Product-related models.
Keeps backward compatibility with existing database tables.
"""
from __future__ import annotations
from typing import Optional
from django.db import models
from parler.models import TranslatableModel, TranslatedFields


class SoftDeleteManager(models.Manager):
    """Manager that filters out soft-deleted objects by default."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
    def all_with_deleted(self):
        return super().get_queryset()


class Badge(TranslatableModel):
    """Product badge (e.g., 'New', 'Sale', 'Popular')."""
    
    translations = TranslatedFields(
        name=models.CharField(
            max_length=255,
            verbose_name='Название',
            null=True,
            blank=True
        )
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный',
        db_index=True
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
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    class Meta:
        verbose_name = 'Бейдж'
        verbose_name_plural = 'Бейджи'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.safe_translation_getter('name', default=f'Badge {self.pk}')


class Unit(TranslatableModel):
    """Unit of measurement (e.g., 'kg', 'litre', 'piece')."""
    
    translations = TranslatedFields(
        name=models.CharField(
            max_length=255,
            verbose_name='Название',
            null=True,
            blank=True
        )
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный',
        db_index=True
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
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    class Meta:
        verbose_name = 'Единица измерения'
        verbose_name_plural = 'Единицы измерения'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.safe_translation_getter('name', default=f'Unit {self.pk}')


class ProductManager(SoftDeleteManager):
    """Custom manager for Product with optimized queries."""
    
    def active(self):
        """Return only active products."""
        return self.get_queryset().filter(is_active=True)
    
    def with_relations(self):
        """Return queryset with common relations prefetched."""
        return self.get_queryset().select_related(
            'badge', 'unit', 'category'
        ).prefetch_related(
            'images', 'barcodes'
        )


class Products(TranslatableModel):
    """
    Product model with translations.
    Kept as 'Products' for backward compatibility with existing database.
    """
    
    unique_id = models.CharField(
        max_length=255,
        verbose_name='Уникальный ID',
        null=True,
        blank=True,
        unique=True
    )

    shelf_location = models.CharField(
        max_length=50,
        verbose_name='Место на полке',
        null=True,
        blank=True,
        db_index=True,
    )
    
    translations = TranslatedFields(
        name=models.CharField(
            max_length=255,
            verbose_name='Название',
            null=True,
            blank=True
        ),
        description=models.TextField(
            verbose_name='Описание',
            null=True,
            blank=True
        ),
        composition=models.TextField(
            verbose_name='Состав',
            null=True,
            blank=True
        ),
        expiration_date=models.CharField(
            max_length=255,
            verbose_name='Срок годности',
            null=True,
            blank=True
        ),
        country=models.CharField(
            max_length=255,
            verbose_name='Страна',
            null=True,
            blank=True
        ),
        grammage=models.CharField(
            max_length=255,
            verbose_name='Граммаж',
            null=True,
            blank=True
        ),
    )
    
    badge = models.ForeignKey(
        Badge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name='Бейдж'
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name='Единица измерения'
    )
    category = models.ForeignKey(
        'categories.Category',
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Категория'
    )
    
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество',
        db_index=True
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Цена'
    )
    price_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Цена со скидкой',
        null=True,
        blank=True
    )
    discount_percentage = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Процент скидки'
    )
    
    is_discount = models.BooleanField(
        default=False,
        verbose_name='Есть скидка',
        db_index=True
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный',
        db_index=True
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
    
    objects = ProductManager()
    all_objects = models.Manager()
    
    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['shelf_location']),
        ]

    def __str__(self) -> str:
        return self.safe_translation_getter('name', default=f'Product {self.pk}')
    
    @property
    def current_price(self):
        """Get current price (discounted if applicable)."""
        if self.is_discount and self.price_discount:
            return self.price_discount
        return self.price
    
    @property
    def is_in_stock(self) -> bool:
        """Check if product is in stock."""
        return self.quantity > 0
    
    def delete(self, *args, hard_delete=False, **kwargs):
        """Soft delete by default."""
        if hard_delete:
            return super().delete(*args, **kwargs)
        self.is_deleted = True
        self.save(update_fields=['is_deleted'])


Product = Products

class ProductBarcode(models.Model):
    """Product barcode."""
    
    product = models.ForeignKey(
        Products,
        on_delete=models.CASCADE,
        related_name='barcodes',
        verbose_name='Продукт'
    )
    barcode = models.CharField(
        max_length=255,
        verbose_name='Штрихкод',
        db_index=True
    )
    barcode_image = models.ImageField(
        upload_to='barcodes/images/',
        null=True,
        blank=True,
        verbose_name='Изображение штрихкода'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный'
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
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Штрихкод продукта'
        verbose_name_plural = 'Штрихкоды продуктов'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self) -> str:
        return f'Barcode {self.barcode}'


class ProductImage(models.Model):
    """Product image."""
    
    product = models.ForeignKey(
        Products,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Продукт'
    )
    image = models.ImageField(
        upload_to='products/images/',
        null=True,
        blank=True,
        verbose_name='Изображение'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный'
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='Удалён',
        db_index=True
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Порядок'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Изображение продукта'
        verbose_name_plural = 'Изображения продуктов'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self) -> str:
        return f'Image #{self.pk}'


class ProductSavedUser(models.Model):
    """User's saved/favorite products."""
    
    product = models.ForeignKey(
        Products,
        on_delete=models.CASCADE,
        related_name='savings',
        verbose_name='Продукт'
    )
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='savings',
        verbose_name='Пользователь'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный',
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    class Meta:
        verbose_name = 'Сохранённый продукт'
        verbose_name_plural = 'Сохранённые продукты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['user']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self) -> str:
        return f'Saved #{self.pk}'
