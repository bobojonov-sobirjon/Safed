from django.contrib import admin

from parler.admin import TranslatableAdmin

from apps.orders.models import (
    Order,
    OrderProduct,
    OrderCourier,
    DeliveryFeeRule,
    OrderFeeSettings,
    BusyDayWorkingHours,
    DeliverySlot,
    DeliveryAddress,
    ClickPayment,
    OrderCancelReason,
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


@admin.register(OrderCancelReason)
class OrderCancelReasonAdmin(TranslatableAdmin):
    list_display = ['code', 'sort_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'translations__name']
    ordering = ['sort_order', 'id']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'status', 'payment_type', 'products_subtotal', 'service_fee_amount',
        'delivery_fee', 'packing_fee', 'estimated_total', 'final_total', 'refund_amount',
        'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'user__phone', 'address', 'entrance', 'apartment', 'cancel_comment']
    ordering = ['-created_at']
    inlines = [OrderProductInline, OrderCourierInline]
    filter_horizontal = ['cancel_reasons']
    readonly_fields = [
        'products_subtotal', 'service_fee_amount', 'estimated_total', 'refund_amount',
        'cash_qr_token', 'qr_confirmed_at', 'delivered_at',
        'created_at', 'updated_at',
    ]


@admin.register(ClickPayment)
class ClickPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'amount', 'state', 'click_trans_id', 'created_at']
    list_filter = ['state']
    search_fields = ['order__id', 'click_trans_id']
    raw_id_fields = ['order']


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


@admin.register(DeliverySlot)
class DeliverySlotAdmin(admin.ModelAdmin):
    list_display = ['id', 'slot_date', 'start_time', 'end_time', 'capacity', 'delivery_fee', 'is_active', 'created_at']
    list_filter = ['slot_date', 'is_active']
    ordering = ['-slot_date', 'start_time']


@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'street', 'house_number', 'is_default', 'updated_at']
    search_fields = ['street', 'user__phone']
    list_filter = ['is_default']


@admin.register(BusyDayWorkingHours)
class BusyDayWorkingHoursAdmin(admin.ModelAdmin):
    list_display = ['id', 'date', 'working_start', 'working_end', 'updated_at']
    list_filter = ['date']
    ordering = ['-date', 'id']
    search_fields = ['date']

@admin.register(DeliveryFeeRule)
class DeliveryFeeRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'min_order_amount', 'max_order_amount', 'fee_amount', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    ordering = ['min_order_amount', 'id']


@admin.register(OrderFeeSettings)
class OrderFeeSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'service_fee_percent', 'packing_fee_amount',
        'min_order_subtotal', 'weight_buffer_percent', 'loyalty_point_currency_value',
        'hourly_delivery_capacity', 'updated_at',
    ]