"""
Product business logic service.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.conf import settings
from django.db import transaction

from apps.categories.models import Category
from apps.core.enums import Language, ProductUnit
from apps.products.models import Products
from apps.products.services.product_write import (
    apply_product_translations,
    assign_product_fields,
    create_product_barcode,
    create_product_record,
    update_product_record,
)


class ProductService:
    """Service class for product operations."""

    CACHE_KEY_PREFIX = 'product'

    @staticmethod
    def get_category_with_descendants(category_id: int) -> List[int]:
        cache_key = f'category_descendants:{category_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            category = Category.objects.get(pk=category_id)
            ids = category.get_all_descendant_ids()
            cache.set(cache_key, ids, settings.CACHE_TTL_MEDIUM)
            return ids
        except Category.DoesNotExist:
            return [category_id]

    @staticmethod
    @transaction.atomic
    def create_product(
        translations: Dict[str, Dict[str, Any]],
        category: Category,
        price: Decimal,
        *,
        product_unit: str = ProductUnit.PIECE.value,
        unit_amount: Decimal = Decimal('1'),
        quantity: int = 0,
        badge=None,
        unit=None,
        shelf_location: Optional[str] = None,
        price_discount=None,
        discount_percentage: int = 0,
        is_discount: bool = False,
        is_active: bool = True,
        barcode_number: Optional[str] = None,
        images: Optional[List] = None,
    ) -> Products:
        product = create_product_record(
            translations=translations,
            category=category,
            price=price,
            product_unit=product_unit,
            unit_amount=unit_amount,
            quantity=quantity,
            badge=badge,
            unit=unit,
            shelf_location=shelf_location,
            price_discount=price_discount,
            discount_percentage=discount_percentage,
            is_discount=is_discount,
            is_active=is_active,
            barcode_number=barcode_number,
            images=images,
        )
        ProductService._invalidate_cache(product)
        return product

    @staticmethod
    @transaction.atomic
    def update_product(
        product: Products,
        translations: Optional[Dict] = None,
        **kwargs,
    ) -> Products:
        update_product_record(product, translations=translations, **kwargs)
        ProductService._invalidate_cache(product)
        return product

    @staticmethod
    def _apply_translations(product: Products, translations: Dict[str, Dict[str, Any]]):
        apply_product_translations(
            product,
            translations,
            product_unit=product.product_unit,
            unit_amount=product.unit_amount,
        )

    @staticmethod
    def _create_barcode(product: Products, barcode_number: Optional[str] = None):
        return create_product_barcode(product, barcode_number)

    @staticmethod
    def _invalidate_cache(product: Products):
        cache.delete(f'product:{product.pk}')
        if product.category_id:
            cache.delete(f'category_products:{product.category_id}')

    @staticmethod
    def get_product_with_relations(product_id: int) -> Optional[Products]:
        cache_key = f'product:{product_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            product = Products.objects.select_related(
                'badge', 'unit', 'category',
            ).prefetch_related('images', 'barcodes').get(pk=product_id, is_deleted=False)
            cache.set(cache_key, product, settings.CACHE_TTL_SHORT)
            return product
        except Products.DoesNotExist:
            return None

    @staticmethod
    def check_user_favorites(user, product_ids: List[int]) -> Dict[int, bool]:
        from apps.products.models import ProductSavedUser

        if not user or not user.is_authenticated:
            return {pid: False for pid in product_ids}
        saved = set(
            ProductSavedUser.objects.filter(
                user=user, product_id__in=product_ids, is_active=True,
            ).values_list('product_id', flat=True)
        )
        return {pid: pid in saved for pid in product_ids}
