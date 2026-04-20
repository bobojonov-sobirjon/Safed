from django.contrib import admin

from apps.orders.models import (
    Order,
    OrderProduct,
    OrderCourier,
    DeliveryFeeRule,
    OrderFeeSettings,
)

class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    extra = 0
    autocomplete_fields = ['product']
    readonly_fields = ['unit_price', 'total_price', 'created_at']


class OrderCourierInline(admin.TabularInline):
    model = OrderCourier
    extra = 0
    autocomplete_fields = ['courier']
    readonly_fields = ['created_at', 'completed_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'status', 'products_subtotal', 'service_fee_amount',
        'delivery_fee', 'packing_fee', 'estimated_total', 'final_total', 'refund_amount',
        'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'user__phone', 'address', 'entrance', 'apartment']
    ordering = ['-created_at']
    inlines = [OrderProductInline, OrderCourierInline]
    readonly_fields = ['products_subtotal', 'service_fee_amount', 'estimated_total', 'refund_amount', 'created_at', 'updated_at']


@admin.register(OrderProduct)
class OrderProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'unit_price', 'total_price', 'created_at']
    list_filter = ['created_at']
    search_fields = ['order__id', 'product__translations__name', 'product__barcodes__barcode']
    autocomplete_fields = ['order', 'product']
    ordering = ['-created_at']


@admin.register(OrderCourier)
class OrderCourierAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'courier', 'completed_at', 'created_at']
    list_filter = ['created_at', 'completed_at']
    search_fields = ['order__id', 'courier__phone']
    autocomplete_fields = ['order', 'courier']
    ordering = ['-created_at']


@admin.register(DeliveryFeeRule)
class DeliveryFeeRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'min_order_amount', 'max_order_amount', 'fee_amount', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    ordering = ['min_order_amount', 'id']


@admin.register(OrderFeeSettings)
class OrderFeeSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'service_fee_percent', 'packing_fee_amount', 'updated_at']