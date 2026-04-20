"""
Product serializers with N+1 query optimization.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Dict, Any, List, Optional
from rest_framework import serializers
from django.conf import settings
from parler.utils.context import switch_language

from .models import Badge, Unit, Products, ProductBarcode, ProductImage, ProductSavedUser
from apps.categories.models import Category
from apps.core.enums import Language


_REQUIRED = {'required': 'Обязательное поле.'}
_LANGS = Language.codes()


def get_product_translations(obj) -> Dict[str, Dict[str, Any]]:
    """Get all translations for a product."""
    fields = ['name', 'description', 'composition', 'expiration_date', 'country', 'grammage']
    result = {}
    for lang in _LANGS:
        if obj.has_translation(lang):
            with switch_language(obj, lang):
                result[lang] = {f: getattr(obj, f, '') or '' for f in fields}
    return result


def get_category_translations(obj) -> Dict[str, str]:
    """Get all translations for a category name."""
    result = {}
    for lang in _LANGS:
        if obj.has_translation(lang):
            with switch_language(obj, lang):
                result[lang] = obj.name or ''
    return result


def get_simple_translations(obj) -> Dict[str, Dict[str, str]]:
    """Get all name translations for Badge/Unit as objects."""
    result = {}
    try:
        translations = obj.translations.all()
        for trans in translations:
            result[trans.language_code] = {'name': trans.name or ''}
    except Exception:
        for lang in _LANGS:
            if obj.has_translation(lang):
                with switch_language(obj, lang):
                    result[lang] = {'name': obj.name or ''}
    return result


# =============================================================================
# Badge Serializers
# =============================================================================

class BadgeSerializer(serializers.ModelSerializer):
    """Badge serializer with translations."""
    name = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']

    def get_name(self, obj) -> Dict[str, Dict[str, str]]:
        return get_simple_translations(obj)


class BadgeCreateUpdateSerializer(serializers.Serializer):
    """Serializer for creating/updating badges with translations."""
    name = serializers.JSONField(required=True, error_messages=_REQUIRED)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_name(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('name должен быть объектом')
        
        valid_langs = set(_LANGS)
        for lang, data in value.items():
            if lang not in valid_langs:
                raise serializers.ValidationError(f'Неподдерживаемый язык: {lang}')
            if not isinstance(data, dict) or 'name' not in data:
                raise serializers.ValidationError(f'Для языка {lang} требуется поле name')
        
        return value


# =============================================================================
# Unit Serializers
# =============================================================================

class UnitSerializer(serializers.ModelSerializer):
    """Unit serializer with translations."""
    name = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']

    def get_name(self, obj) -> Dict[str, Dict[str, str]]:
        return get_simple_translations(obj)


class UnitCreateUpdateSerializer(serializers.Serializer):
    """Serializer for creating/updating units with translations."""
    name = serializers.JSONField(required=True, error_messages=_REQUIRED)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_name(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('name должен быть объектом')
        
        valid_langs = set(_LANGS)
        for lang, data in value.items():
            if lang not in valid_langs:
                raise serializers.ValidationError(f'Неподдерживаемый язык: {lang}')
            if not isinstance(data, dict) or 'name' not in data:
                raise serializers.ValidationError(f'Для языка {lang} требуется поле name')
        
        return value


# =============================================================================
# ProductBarcode Serializers
# =============================================================================

class ProductBarcodeSerializer(serializers.ModelSerializer):
    barcode_image = serializers.SerializerMethodField()

    class Meta:
        model = ProductBarcode
        fields = ['id', 'product', 'barcode', 'barcode_image', 'is_active', 'created_at', 'updated_at']

    def get_barcode_image(self, obj) -> Optional[str]:
        if obj.barcode_image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.barcode_image.url) if request else obj.barcode_image.url
        return None


class ProductBarcodeUpdateSerializer(serializers.Serializer):
    barcode = serializers.CharField(required=True, max_length=255, error_messages=_REQUIRED)


# =============================================================================
# ProductImage Serializers
# =============================================================================

class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'product', 'image', 'is_active', 'created_at', 'updated_at']

    def get_image(self, obj) -> Optional[str]:
        if obj.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class ProductImageUpdateSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True, error_messages=_REQUIRED)


# =============================================================================
# Category Serializers
# =============================================================================

class CategoryMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj) -> Dict[str, str]:
        return get_category_translations(obj)


class CategoryWithHierarchySerializer(serializers.Serializer):
    """Category with parent hierarchy and is_chosen field."""
    
    def to_representation(self, category) -> Optional[Dict]:
        chosen_id = self.context.get('chosen_category_id')
        return self._build_hierarchy(category, chosen_id)
    
    def _build_category_data(self, cat, is_chosen: bool = False) -> Dict:
        return {
            'id': cat.id,
            'name': get_category_translations(cat),
            'is_chosen': is_chosen,
        }
    
    def _build_hierarchy(self, category, chosen_id) -> Optional[Dict]:
        if not category:
            return None
        
        root = category
        while root.parent:
            root = root.parent
        
        return self._build_tree(root, chosen_id)
    
    def _build_tree(self, category, chosen_id) -> Dict:
        is_chosen = category.id == chosen_id
        data = self._build_category_data(category, is_chosen)
        
        children_qs = getattr(category, '_prefetched_children', None)
        if children_qs is None:
            children_qs = category.children.filter(is_active=True, is_deleted=False).order_by('order')
        
        children = list(children_qs)
        if children:
            data['children'] = [self._build_tree(child, chosen_id) for child in children]
        
        return data


# =============================================================================
# Product Serializers
# =============================================================================

class ProductListSerializer(serializers.ModelSerializer):
    """
    Optimized product serializer.
    Use with prefetch_related and select_related for best performance.
    """
    translations = serializers.SerializerMethodField()
    badge = BadgeSerializer(read_only=True)
    unit = UnitSerializer(read_only=True)
    category = serializers.SerializerMethodField()
    barcodes = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    is_favourite = serializers.SerializerMethodField()

    class Meta:
        model = Products
        fields = [
            'id', 'translations', 'badge', 'unit', 'shelf_location', 'quantity', 'price',
            'price_discount', 'discount_percentage', 'is_discount', 'is_active',
            'category', 'barcodes', 'images', 'is_favourite', 'created_at', 'updated_at',
        ]

    def get_translations(self, obj) -> Dict:
        return get_product_translations(obj)

    def get_category(self, obj) -> Optional[Dict]:
        if not obj.category:
            return None
        return CategoryWithHierarchySerializer(
            obj.category,
            context={'chosen_category_id': obj.category.id}
        ).data

    def get_barcodes(self, obj) -> List[Dict]:
        if hasattr(obj, '_prefetched_objects_cache') and 'barcodes' in obj._prefetched_objects_cache:
            barcodes = [b for b in obj.barcodes.all() if not b.is_deleted]
        else:
            barcodes = obj.barcodes.filter(is_deleted=False)
        return ProductBarcodeSerializer(barcodes, many=True, context=self.context).data

    def get_images(self, obj) -> List[Dict]:
        if hasattr(obj, '_prefetched_objects_cache') and 'images' in obj._prefetched_objects_cache:
            images = [i for i in obj.images.all() if i.is_active and not i.is_deleted]
        else:
            images = obj.images.filter(is_active=True, is_deleted=False)
        return ProductImageSerializer(images, many=True, context=self.context).data

    def get_is_favourite(self, obj) -> bool:
        favorites_map = self.context.get('favorites_map')
        if favorites_map is not None:
            return favorites_map.get(obj.id, False)
        
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ProductSavedUser.objects.filter(
                product=obj, 
                user=request.user, 
                is_active=True
            ).exists()
        return False


class ProductCreateSerializer(serializers.Serializer):
    """Serializer for creating products."""
    translations = serializers.JSONField(required=True, error_messages=_REQUIRED)
    badge = serializers.PrimaryKeyRelatedField(
        queryset=Badge.objects.filter(is_deleted=False), 
        required=False, 
        allow_null=True
    )
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.filter(is_deleted=False), 
        required=False, 
        allow_null=True
    )
    quantity = serializers.IntegerField(required=False, default=0, min_value=0)
    price = serializers.DecimalField(
        required=True, 
        max_digits=12, 
        decimal_places=2, 
        min_value=Decimal('0'),
        error_messages=_REQUIRED
    )
    price_discount = serializers.DecimalField(
        required=False, 
        max_digits=12, 
        decimal_places=2, 
        allow_null=True,
        min_value=Decimal('0')
    )
    discount_percentage = serializers.IntegerField(
        required=False, 
        default=0, 
        allow_null=True,
        min_value=0,
        max_value=100
    )
    is_discount = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_deleted=False), 
        required=False, 
        allow_null=True
    )
    barcode_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    shelf_location = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)

    def validate_translations(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError('translations должен быть объектом')
        return value

    def validate(self, attrs):
        if not self.partial and 'category' not in attrs:
            raise serializers.ValidationError({'category': 'Обязательное поле.'})
        return attrs


# =============================================================================
# ProductSavedUser Serializers
# =============================================================================

class ProductSavedUserSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = ProductSavedUser
        fields = ['id', 'product', 'user', 'created_at']
