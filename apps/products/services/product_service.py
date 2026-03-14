"""
Product business logic service.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from apps.products.models import Products, ProductImage, ProductBarcode
from apps.categories.models import Category
from apps.core.enums import Language
from .barcode import generate_barcode_number, generate_barcode_image


class ProductService:
    """Service class for product operations."""
    
    CACHE_KEY_PREFIX = 'product'
    
    @staticmethod
    def get_category_with_descendants(category_id: int) -> List[int]:
        """
        Get category ID and all its descendant IDs.
        Uses caching for performance.
        """
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
        price: 'Decimal',
        quantity: int = 0,
        badge=None,
        unit=None,
        price_discount=None,
        discount_percentage: int = 0,
        is_discount: bool = False,
        is_active: bool = True,
        barcode_number: Optional[str] = None,
        images: List = None,
    ) -> Products:
        """Create a new product with translations, barcode, and images."""
        product = Products.objects.create(
            badge=badge,
            unit=unit,
            category=category,
            quantity=quantity,
            price=price,
            price_discount=price_discount,
            discount_percentage=discount_percentage,
            is_discount=is_discount,
            is_active=is_active,
        )
        
        ProductService._apply_translations(product, translations)
        
        ProductService._create_barcode(product, barcode_number)
        
        if images:
            ProductService._create_images(product, images)
        
        ProductService._invalidate_cache(product)
        
        return product
    
    @staticmethod
    @transaction.atomic
    def update_product(
        product: Products,
        translations: Optional[Dict] = None,
        **kwargs
    ) -> Products:
        """Update an existing product."""
        for field in ['quantity', 'price', 'price_discount', 'discount_percentage', 
                      'is_discount', 'is_active']:
            if field in kwargs and kwargs[field] is not None:
                setattr(product, field, kwargs[field])
        
        if 'badge' in kwargs:
            product.badge = kwargs['badge']
        if 'unit' in kwargs:
            product.unit = kwargs['unit']
        if 'category' in kwargs and kwargs['category'] is not None:
            product.category = kwargs['category']
        
        product.save()
        
        if translations:
            ProductService._apply_translations(product, translations)
        
        ProductService._invalidate_cache(product)
        
        return product
    
    @staticmethod
    def _apply_translations(product: Product, translations: Dict[str, Dict[str, Any]]):
        """Apply translations to product."""
        fields = ['name', 'description', 'composition', 'expiration_date', 'country', 'grammage']
        
        for lang, trans in (translations or {}).items():
            if isinstance(trans, dict) and lang in Language.codes():
                product.set_current_language(lang)
                for field in fields:
                    if field in trans:
                        value = trans[field] if trans[field] is not None else ''
                        setattr(product, field, value)
                product.save()
    
    @staticmethod
    def _create_barcode(product: Product, barcode_number: Optional[str] = None):
        """Create barcode for product."""
        if not barcode_number:
            barcode_number = generate_barcode_number()
        
        img_file = generate_barcode_image(barcode_number)
        barcode = ProductBarcode.objects.create(
            product=product,
            barcode=barcode_number
        )
        
        if img_file:
            barcode.barcode_image.save(f'{barcode_number}.png', img_file, save=True)
        
        return barcode
    
    @staticmethod
    def _create_images(product: Product, images: List):
        """Create images for product using bulk_create."""
        image_objects = [
            ProductImage(product=product, image=img, order=idx)
            for idx, img in enumerate(images)
        ]
        ProductImage.objects.bulk_create(image_objects)
    
    @staticmethod
    def _invalidate_cache(product: Product):
        """Invalidate product-related caches."""
        cache.delete(f'product:{product.pk}')
        if product.category_id:
            cache.delete(f'category_products:{product.category_id}')
    
    @staticmethod
    def get_product_with_relations(product_id: int) -> Optional[Products]:
        """Get product with all relations prefetched."""
        cache_key = f'product:{product_id}'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            product = Products.objects.select_related(
                'badge', 'unit', 'category'
            ).prefetch_related(
                'images', 'barcodes'
            ).get(pk=product_id, is_deleted=False)
            
            cache.set(cache_key, product, settings.CACHE_TTL_SHORT)
            return product
        except Product.DoesNotExist:
            return None
    
    @staticmethod
    def check_user_favorites(user, product_ids: List[int]) -> Dict[int, bool]:
        """
        Check which products are in user's favorites.
        Returns a dict mapping product_id to is_favorite.
        """
        from apps.products.models import ProductSavedUser
        
        if not user or not user.is_authenticated:
            return {pid: False for pid in product_ids}
        
        saved = set(
            ProductSavedUser.objects.filter(
                user=user,
                product_id__in=product_ids,
                is_active=True
            ).values_list('product_id', flat=True)
        )
        
        return {pid: pid in saved for pid in product_ids}
