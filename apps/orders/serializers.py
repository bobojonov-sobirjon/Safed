"""
Order serializers with N+1 query optimization.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Dict, Any, List, Optional
from rest_framework import serializers

from .models import Order, OrderProduct, OrderCourier, DeliveryFeeRule, OrderFeeSettings
from apps.products.models import Products
from apps.products.serializers import ProductListSerializer
from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus


_REQUIRED = {'required': 'Обязательное поле.'}


# =============================================================================
# User Serializers
# =============================================================================

class UserMinSerializer(serializers.ModelSerializer):
    """Minimal user serializer for embedding in other serializers."""
    
    class Meta:
        model = CustomUser
        fields = ['id', 'phone', 'first_name', 'last_name', 'is_active']
        read_only_fields = fields


# =============================================================================
# Order Product Serializers
# =============================================================================

class OrderProductItemSerializer(serializers.Serializer):
    """Request body item for order products."""
    product_id = serializers.IntegerField(required=True, error_messages=_REQUIRED)
    quantity = serializers.IntegerField(required=True, min_value=1, error_messages=_REQUIRED)
    total_price = serializers.DecimalField(
        required=True, 
        max_digits=14, 
        decimal_places=2, 
        min_value=Decimal('0'),
        error_messages=_REQUIRED
    )


class OrderProductSerializer(serializers.ModelSerializer):
    """Serializer for order products with product details."""
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product = serializers.SerializerMethodField()

    class Meta:
        model = OrderProduct
        fields = ['id', 'product_id', 'product', 'quantity', 'unit_price', 'total_price', 'created_at']

    def get_product(self, obj) -> Optional[Dict]:
        if obj.product:
            return ProductListSerializer(obj.product, context=self.context).data
        return None


# =============================================================================
# Order Courier Serializers
# =============================================================================

class OrderCourierSerializer(serializers.ModelSerializer):
    """Serializer for order couriers."""
    courier_data = serializers.SerializerMethodField()

    class Meta:
        model = OrderCourier
        fields = ['id', 'courier_data', 'completed_at', 'created_at']

    def get_courier_data(self, obj) -> Optional[Dict]:
        if obj.courier:
            return UserMinSerializer(obj.courier).data
        return None


# =============================================================================
# Order Create/Update Serializers
# =============================================================================

class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating orders."""
    products_data = serializers.ListField(
        child=OrderProductItemSerializer(),
        required=True,
        min_length=1,
        error_messages=_REQUIRED,
    )
    lat = serializers.DecimalField(
        required=True, 
        max_digits=10, 
        decimal_places=7, 
        allow_null=False,
        error_messages=_REQUIRED,
    )
    long = serializers.DecimalField(
        required=True, 
        max_digits=10, 
        decimal_places=7, 
        allow_null=False,
        error_messages=_REQUIRED,
    )
    address = serializers.CharField(required=True, allow_blank=False, max_length=1000, error_messages=_REQUIRED)
    entrance = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    apartment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=5000)

    def validate_products_data(self, value):
        if not value:
            raise serializers.ValidationError('Минимум один продукт')
        
        product_ids = [item['product_id'] for item in value]
        existing_ids = set(
            Products.objects.filter(
                pk__in=product_ids, 
                is_active=True, 
                is_deleted=False
            ).values_list('id', flat=True)
        )
        
        missing = set(product_ids) - existing_ids
        if missing:
            raise serializers.ValidationError(
                f'Продукты не найдены: {", ".join(map(str, missing))}'
            )
        return value


class OrderUpdateSerializer(serializers.Serializer):
    """Serializer for updating orders."""
    products_data = serializers.ListField(
        child=OrderProductItemSerializer(), 
        required=False,
        min_length=1
    )
    lat = serializers.DecimalField(
        required=False, 
        max_digits=10, 
        decimal_places=7, 
        allow_null=True
    )
    long = serializers.DecimalField(
        required=False, 
        max_digits=10, 
        decimal_places=7, 
        allow_null=True
    )
    address = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    entrance = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    apartment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=5000)

    def validate_products_data(self, value):
        if value is not None:
            product_ids = [item['product_id'] for item in value]
            existing_ids = set(
                Products.objects.filter(
                    pk__in=product_ids, 
                    is_active=True, 
                    is_deleted=False
                ).values_list('id', flat=True)
            )
            
            missing = set(product_ids) - existing_ids
            if missing:
                raise serializers.ValidationError(
                    f'Продукты не найдены: {", ".join(map(str, missing))}'
                )
        return value


# =============================================================================
# Order List Serializers
# =============================================================================

class OrderListSerializer(serializers.ModelSerializer):
    """
    Optimized order serializer.
    Use with select_related and prefetch_related for best performance.
    """
    user_data = serializers.SerializerMethodField()
    order_products = serializers.SerializerMethodField()
    order_couriers = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'user_data', 'lat', 'long', 'address', 'entrance', 'apartment', 'comment', 'status', 'status_display',
            'total_amount',
            'products_subtotal', 'service_fee_percent', 'service_fee_amount',
            'delivery_fee', 'packing_fee', 'estimated_total',
            'final_total', 'refund_amount',
            'order_products', 'order_couriers', 'created_at', 'updated_at',
        ]

    def get_user_data(self, obj) -> Optional[Dict]:
        if obj.user:
            return UserMinSerializer(obj.user).data
        return None

    def get_order_products(self, obj) -> List[Dict]:
        if hasattr(obj, '_prefetched_objects_cache') and 'order_products' in obj._prefetched_objects_cache:
            order_products = obj.order_products.all()
        else:
            order_products = obj.order_products.select_related('product__badge', 'product__unit', 'product__category')
        return OrderProductSerializer(order_products, many=True, context=self.context).data

    def get_order_couriers(self, obj) -> List[Dict]:
        if hasattr(obj, '_prefetched_objects_cache') and 'order_couriers' in obj._prefetched_objects_cache:
            order_couriers = obj.order_couriers.all()
        else:
            order_couriers = obj.order_couriers.select_related('courier')
        return OrderCourierSerializer(order_couriers, many=True, context=self.context).data

    def get_status_display(self, obj) -> str:
        status_map = dict(OrderStatus.choices())
        return status_map.get(obj.status, obj.status)


# =============================================================================
# Other Serializers
# =============================================================================

class AddCourierSerializer(serializers.Serializer):
    """Serializer for adding courier to order."""
    courier_id = serializers.IntegerField(required=True, error_messages=_REQUIRED)

    def validate_courier_id(self, value):
        from apps.core.enums import UserGroup
        
        try:
            user = CustomUser.objects.get(pk=value)
            if not user.is_in_group(UserGroup.COURIER.value):
                raise serializers.ValidationError('Пользователь не является курьером')
            return value
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError('Пользователь не найден')


class StatusChangeSerializer(serializers.Serializer):
    """Serializer for changing order status."""
    status = serializers.ChoiceField(
        choices=[s.value for s in OrderStatus],
        required=True,
        error_messages=_REQUIRED,
    )


class FinalizePricingSerializer(serializers.Serializer):
    final_total = serializers.DecimalField(required=True, max_digits=14, decimal_places=2, min_value=Decimal('0.00'))


# =============================================================================
# Fee Settings / Delivery Rules (Admin API)
# =============================================================================

class OrderFeeSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderFeeSettings
        fields = ['id', 'service_fee_percent', 'packing_fee_amount', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class DeliveryFeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryFeeRule
        fields = ['id', 'min_order_amount', 'max_order_amount', 'fee_amount', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
