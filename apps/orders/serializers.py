"""
Order serializers with N+1 query optimization.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Dict, Any, List, Optional
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import (
    Order,
    OrderProduct,
    OrderCourier,
    DeliveryFeeRule,
    OrderFeeSettings,
    BusySlot,
    DeliverySlot,
    DeliveryAddress,
    OrderCancelReason,
)
from apps.products.models import Products
from apps.products.serializers import ProductListSerializer
from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, PaymentStatus, PaymentType, ProductUnit, SaleUnit
from apps.core.geo import GEO_COORD_DECIMAL_PLACES, GEO_COORD_MAX_DIGITS
from apps.products.fields import ProductUnitChoiceField
from apps.products.product_unit_specs import get_product_unit_spec
from apps.products.unit_pricing import UnitPricingError, compute_line_pricing
from apps.orders.pricing import settlement_baseline_amount, settlement_type_for


_REQUIRED = {'required': 'Обязательное поле.'}

PARLER_LANGUAGES = ['uz', 'ru', 'en']


def cancel_reason_translations(obj: OrderCancelReason) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    for lang in PARLER_LANGUAGES:
        if obj.has_translation(lang):
            obj.set_current_language(lang)
            result[lang] = {'name': obj.name or ''}
    return result


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

class BusySlotFlatSerializer(serializers.ModelSerializer):
    """DB row: blocked interval."""

    class Meta:
        model = BusySlot
        fields = ['id', 'date', 'start_time', 'end_time', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'start_time': {'format': '%H:%M'},
            'end_time': {'format': '%H:%M'},
        }


class DeliveryDaySetupSerializer(serializers.Serializer):
    """
  Admin: ish kunini belgilash (POST delivery-slots / busy-slots — bir xil).
  `start_time`/`end_time` — eski busy-slots nomlari (working_start/working_end bilan bir xil).
    """
    date = serializers.DateField(required=True)
    working_start = serializers.CharField(required=False, allow_blank=True, max_length=8)
    working_end = serializers.CharField(required=False, allow_blank=True, max_length=8)
    start_time = serializers.CharField(
        required=False, allow_blank=True, max_length=8,
        help_text='Eski nom (busy-slots). = working_start',
    )
    end_time = serializers.CharField(
        required=False, allow_blank=True, max_length=8,
        help_text='Eski nom (busy-slots). = working_end',
    )

    def validate(self, attrs):
        from apps.orders.busy_slot_schedule import parse_time_flexible

        ws_raw = (attrs.get('working_start') or attrs.get('start_time') or '').strip()
        we_raw = (attrs.get('working_end') or attrs.get('end_time') or '').strip()
        if not ws_raw or not we_raw:
            raise serializers.ValidationError(
                'Укажите working_start и working_end (или start_time и end_time).'
            )
        try:
            st = parse_time_flexible(ws_raw)
            en = parse_time_flexible(we_raw)
        except (ValueError, KeyError):
            raise serializers.ValidationError(
                {'working_start': 'Некорректное время. Формат HH:MM или HH-MM.'}
            )
        if en <= st:
            raise serializers.ValidationError({'working_end': 'Должно быть позже начала.'})
        attrs['working_start'] = st
        attrs['working_end'] = en
        return attrs


class BusySlotPatchSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    start_time = serializers.CharField(required=False, max_length=8)
    end_time = serializers.CharField(required=False, max_length=8)

    def validate(self, attrs):
        from apps.orders.busy_slot_schedule import parse_time_flexible

        obj: BusySlot = self.context['busy_slot']
        if not attrs:
            raise serializers.ValidationError('No fields provided.')
        d = attrs.get('date', obj.date)
        st_raw = attrs.get('start_time', None)
        en_raw = attrs.get('end_time', None)
        if st_raw == '':
            st_raw = None
        if en_raw == '':
            en_raw = None
        try:
            st = obj.start_time if st_raw is None else parse_time_flexible(st_raw)
            en = obj.end_time if en_raw is None else parse_time_flexible(en_raw)
        except ValueError as exc:
            raise serializers.ValidationError('Invalid time. Use HH:MM or HH-MM.') from exc
        if en <= st:
            raise serializers.ValidationError({'end_time': 'Must be after start_time.'})
        attrs['date'] = d
        attrs['_start'] = st
        attrs['_end'] = en
        return attrs


class OrderProductItemSerializer(serializers.Serializer):
    """Одна строка корзины в `products_data[]`."""
    product_id = serializers.IntegerField(
        required=True,
        error_messages=_REQUIRED,
        help_text='ID товара из `GET /products/` (поле `id`). Не order id, не line_id.',
    )
    quantity = serializers.DecimalField(
        required=True,
        max_digits=12,
        decimal_places=3,
        min_value=Decimal('0.001'),
        error_messages=_REQUIRED,
        help_text='Сколько заказать. piece — целое; kg/liter — можно 1.5; ml/gram — в мл/г (см. unit-options).',
    )
    product_unit = ProductUnitChoiceField(
        required=False,
        allow_null=True,
        help_text='piece | kg | gram | liter | ml. Пусто = единица из карточки товара. GET /products/unit-options/',
    )


class OrderProductSerializer(serializers.ModelSerializer):
    """Serializer for order products with product details."""
    product_id = serializers.IntegerField(
        source='product.id',
        read_only=True,
        help_text='**Katalog mahsulot ID** (`Products.id`). Yig‘ish URL uchun emas.',
    )
    product = serializers.SerializerMethodField()
    ordered_quantity = serializers.SerializerMethodField()

    class Meta:
        model = OrderProduct
        fields = [
            'id', 'product_id', 'product',
            'ordered_quantity', 'quantity', 'product_unit', 'normalized_quantity',
            'unit_price', 'total_price', 'created_at',
        ]
        extra_kwargs = {
            'id': {
                'help_text': (
                    '**Buyurtma qatori ID** (`OrderProduct.id`). '
                    'PATCH `/orders/{id}/picking-lines/{line_id}/` da `line_id` — shu maydon. '
                    '`product_id` emas.'
                ),
            },
            'ordered_quantity': {
                'help_text': 'Buyurtma berilgandagi miqdor (o‘zgarmaydi).',
            },
            'quantity': {
                'help_text': 'Joriy miqdor (`product_unit` bo‘yicha).',
            },
            'product_unit': {
                'help_text': 'Birlik: piece, kg, gram, liter, ml.',
            },
            'normalized_quantity': {
                'help_text': 'Katalog `product_unit` bo‘yicha normalizatsiya (narx/stock).',
            },
        }

    def get_ordered_quantity(self, obj) -> str:
        oq = obj.ordered_quantity if obj.ordered_quantity is not None else obj.quantity
        return str(oq)

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
    """Checkout: `products_data` + адрес + слот + `payment_type`. См. описание эндпоинта."""
    products_data = serializers.ListField(
        child=OrderProductItemSerializer(),
        required=True,
        min_length=1,
        error_messages=_REQUIRED,
        help_text='Минимум 1 товар. `total_price` в строках не передавать.',
    )
    lat = serializers.DecimalField(
        required=False,
        max_digits=GEO_COORD_MAX_DIGITS,
        decimal_places=GEO_COORD_DECIMAL_PLACES,
        allow_null=True,
        help_text='Широта. Нужно с `long` и `address`, если нет `delivery_address_id`.',
    )
    long = serializers.DecimalField(
        required=False,
        max_digits=GEO_COORD_MAX_DIGITS,
        decimal_places=GEO_COORD_DECIMAL_PLACES,
        allow_null=True,
        help_text='Долгота. Вместе с `lat` и `address`.',
    )
    address = serializers.CharField(
        required=False, allow_blank=True, max_length=1000,
        help_text='Текст адреса. Альтернатива: `delivery_address_id`.',
    )
    delivery_address_id = serializers.IntegerField(
        required=False, allow_null=True,
        help_text='ID из `GET /addresses/`. Вместо lat/long/address.',
    )
    entrance = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    apartment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=5000)
    delivery_date = serializers.DateField(
        required=False, allow_null=True,
        help_text='Из delivery-slots → `date`. Вместе с delivery_time_start/end.',
    )
    delivery_time_start = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=8,
        help_text='Начало слота, напр. `09:00` (поле `start` в slots[]).',
    )
    delivery_time_end = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=8,
        help_text='Конец слота, напр. `10:00` (поле `end` в slots[]).',
    )
    loyalty_points_to_use = serializers.IntegerField(
        required=False, default=0, min_value=0,
        help_text='Баллы лояльности (скидка; макс. 50% базы и баланс пользователя).',
    )
    leave_at_door = serializers.BooleanField(required=False, default=False)
    payment_type = serializers.ChoiceField(
        choices=[pt.value for pt in PaymentType],
        required=True,
        error_messages=_REQUIRED,
        help_text='`card` → затем POST /orders/{id}/click-payment/. `cash` — при доставке.',
    )

    def validate(self, attrs):
        user = self.context['request'].user
        addr_id = attrs.get('delivery_address_id')
        if addr_id:
            if not DeliveryAddress.objects.filter(pk=addr_id, user=user).exists():
                raise serializers.ValidationError({'delivery_address_id': 'Адрес не найден.'})
        else:
            if attrs.get('lat') is None or attrs.get('long') is None or not (attrs.get('address') or '').strip():
                raise serializers.ValidationError(
                    'Укажите lat, long и address или передайте delivery_address_id.'
                )

        dd = attrs.get('delivery_date')
        ts = (attrs.get('delivery_time_start') or '').strip() if attrs.get('delivery_time_start') is not None else ''
        te = (attrs.get('delivery_time_end') or '').strip() if attrs.get('delivery_time_end') is not None else ''
        has_any = dd is not None or bool(ts) or bool(te)
        if has_any:
            if dd is None or not ts or not te:
                raise serializers.ValidationError(
                    'Поля delivery_date, delivery_time_start и delivery_time_end нужно передавать вместе.'
                )
            from apps.orders.busy_slot_schedule import parse_time_flexible, validate_delivery_window
            try:
                st = parse_time_flexible(ts)
                en = parse_time_flexible(te)
            except ValueError:
                raise serializers.ValidationError({'delivery_time_start': 'Некорректное время. Формат HH:MM или HH-MM.'})
            msg = validate_delivery_window(dd, st, en)
            if msg:
                raise serializers.ValidationError(msg)
            attrs['delivery_time_start'] = st
            attrs['delivery_time_end'] = en
        return attrs

    def validate_products_data(self, value):
        return _validate_cart_product_lines(value, check_min_order=True)


class OrderUpdateSerializer(serializers.Serializer):
    """Serializer for updating orders (status `created` only for lines)."""
    products_data = serializers.ListField(
        child=OrderProductItemSerializer(),
        required=False,
        min_length=1,
    )
    lat = serializers.DecimalField(
        required=False,
        max_digits=GEO_COORD_MAX_DIGITS,
        decimal_places=GEO_COORD_DECIMAL_PLACES,
        allow_null=True,
    )
    long = serializers.DecimalField(
        required=False,
        max_digits=GEO_COORD_MAX_DIGITS,
        decimal_places=GEO_COORD_DECIMAL_PLACES,
        allow_null=True,
    )
    address = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    delivery_address_id = serializers.IntegerField(required=False, allow_null=True)
    entrance = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    apartment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=5000)
    delivery_date = serializers.DateField(required=False, allow_null=True)
    delivery_time_start = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=8)
    delivery_time_end = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=8)
    loyalty_points_to_use = serializers.IntegerField(required=False, min_value=0)
    leave_at_door = serializers.BooleanField(required=False)

    def validate(self, attrs):
        user = self.context['request'].user
        raw = getattr(self, 'initial_data', None) or {}
        if attrs.get('delivery_address_id'):
            if not DeliveryAddress.objects.filter(pk=attrs['delivery_address_id'], user=user).exists():
                raise serializers.ValidationError({'delivery_address_id': 'Адрес не найден.'})
        if not any(k in raw for k in ('delivery_date', 'delivery_time_start', 'delivery_time_end')):
            return attrs
        dd = attrs.get('delivery_date')
        ts = (attrs.get('delivery_time_start') or '').strip() if attrs.get('delivery_time_start') is not None else ''
        te = (attrs.get('delivery_time_end') or '').strip() if attrs.get('delivery_time_end') is not None else ''
        if dd is None or not ts or not te:
            raise serializers.ValidationError(
                'Поля delivery_date, delivery_time_start и delivery_time_end нужно передавать вместе.'
            )
        from apps.orders.busy_slot_schedule import parse_time_flexible, validate_delivery_window
        try:
            st = parse_time_flexible(ts)
            en = parse_time_flexible(te)
        except ValueError:
            raise serializers.ValidationError({'delivery_time_start': 'Некорректное время. Формат HH:MM или HH-MM.'})
        oid = self.context.get('order_id')
        msg = validate_delivery_window(dd, st, en, exclude_order_id=oid)
        if msg:
            raise serializers.ValidationError(msg)
        attrs['delivery_time_start'] = st
        attrs['delivery_time_end'] = en
        return attrs

    def validate_products_data(self, value):
        return _validate_cart_product_lines(value, check_min_order=True)


# =============================================================================
# Order List Serializers
# =============================================================================

def _order_time_hhmm(value) -> Optional[str]:
    if value is None:
        return None
    return value.strftime('%H:%M')


def _decimal_str(value) -> str:
    if value is None:
        return '0.00'
    return str(Decimal(str(value)).quantize(Decimal('0.01')))


class OrderPricingSerializer(serializers.Serializer):
    """Снимок цен заказа (все суммы в UZS)."""
    total_amount = serializers.CharField()
    products_subtotal = serializers.CharField()
    buffer_amount = serializers.CharField()
    service_fee_percent = serializers.CharField()
    service_fee_amount = serializers.CharField()
    delivery_fee = serializers.CharField()
    packing_fee = serializers.CharField()
    estimated_total = serializers.CharField()
    final_total = serializers.CharField(allow_null=True)
    refund_amount = serializers.CharField()
    payment_type = serializers.CharField()
    payment_status = serializers.CharField()
    loyalty_points_used = serializers.IntegerField()
    loyalty_discount_amount = serializers.CharField()
    original_estimated_total = serializers.CharField(allow_null=True)
    paid_amount = serializers.CharField(allow_null=True)
    adjustment_balance = serializers.CharField()
    settlement_type = serializers.CharField()
    extra_payment_due = serializers.CharField()
    baseline_amount = serializers.CharField()
    baseline_label = serializers.CharField()


class OrderCancelReasonSerializer(serializers.ModelSerializer):
    """Tayyor sabablar ro‘yxati (cancel form)."""
    name = serializers.SerializerMethodField()

    class Meta:
        model = OrderCancelReason
        fields = ['id', 'code', 'name', 'sort_order']

    def get_name(self, obj) -> Dict[str, Dict[str, str]]:
        return cancel_reason_translations(obj)


class OrderUserCancelSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    reason_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        help_text='Bir yoki bir nechta tayyor sabab ID (`GET /orders/cancel-reasons/`).',
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        comment = (attrs.get('comment') or '').strip()
        raw_ids = attrs.get('reason_ids') or []
        reason_ids = list(dict.fromkeys(raw_ids))
        if not comment and not reason_ids:
            raise serializers.ValidationError(
                'Укажите comment и/или reason_ids (хотя бы одно).'
            )
        attrs['comment'] = comment
        attrs['reason_ids'] = reason_ids
        return attrs


class OrderCancellationSerializer(serializers.Serializer):
    comment = serializers.CharField(allow_blank=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    reasons = OrderCancelReasonSerializer(many=True)


def build_order_cancellation_payload(order: Order) -> Optional[Dict[str, Any]]:
    if order.status != OrderStatus.CANCELLED.value:
        return None
    if hasattr(order, '_prefetched_objects_cache') and 'cancel_reasons' in order._prefetched_objects_cache:
        reasons = order.cancel_reasons.all()
    else:
        reasons = order.cancel_reasons.order_by('sort_order', 'id')
    return {
        'comment': order.cancel_comment or '',
        'cancelled_at': order.cancelled_at,
        'reasons': OrderCancelReasonSerializer(reasons, many=True).data,
    }


class OrderDeliverySlotSerializer(serializers.Serializer):
    """Время и место доставки."""
    date = serializers.DateField(allow_null=True)
    time_start = serializers.CharField(allow_null=True)
    time_end = serializers.CharField(allow_null=True)
    delivery_slot_id = serializers.IntegerField(allow_null=True)
    delivery_address_id = serializers.IntegerField(allow_null=True)
    saved_address = serializers.JSONField(allow_null=True)
    lat = serializers.CharField(allow_null=True)
    long = serializers.CharField(allow_null=True)
    address = serializers.CharField(allow_null=True)
    entrance = serializers.CharField(allow_null=True)
    apartment = serializers.CharField(allow_null=True)
    leave_at_door = serializers.BooleanField()


def _baseline_label(order: Order) -> str:
    if order.paid_amount is not None:
        if order.payment_type == PaymentType.CARD.value:
            return 'paid_by_card'
        return 'paid_cash'
    if order.payment_type == PaymentType.CASH.value:
        return 'quoted_at_checkout_cash'
    return 'quoted_at_checkout'


def build_order_pricing_payload(order: Order) -> Dict[str, Any]:
    adj = Decimal(str(order.adjustment_balance or 0)).quantize(Decimal('0.01'))
    st = settlement_type_for(order)
    baseline = settlement_baseline_amount(order)
    return {
        'total_amount': _decimal_str(order.total_amount),
        'products_subtotal': _decimal_str(order.products_subtotal),
        'buffer_amount': _decimal_str(order.buffer_amount),
        'service_fee_percent': _decimal_str(order.service_fee_percent),
        'service_fee_amount': _decimal_str(order.service_fee_amount),
        'delivery_fee': _decimal_str(order.delivery_fee),
        'packing_fee': _decimal_str(order.packing_fee),
        'estimated_total': _decimal_str(order.estimated_total),
        'final_total': _decimal_str(order.final_total) if order.final_total is not None else None,
        'refund_amount': _decimal_str(order.refund_amount),
        'payment_type': order.payment_type,
        'payment_status': order.payment_status,
        'loyalty_points_used': int(order.loyalty_points_used or 0),
        'loyalty_discount_amount': _decimal_str(order.loyalty_discount_amount),
        'original_estimated_total': (
            _decimal_str(order.original_estimated_total)
            if order.original_estimated_total is not None else None
        ),
        'paid_amount': _decimal_str(order.paid_amount) if order.paid_amount is not None else None,
        'adjustment_balance': _decimal_str(adj),
        'settlement_type': st,
        'extra_payment_due': _decimal_str(adj) if adj > 0 else '0.00',
        'baseline_amount': _decimal_str(baseline),
        'baseline_label': _baseline_label(order),
    }


class OrderPickingLineSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal('0.001'),
        help_text='Miqdor: dona (`2`) yoki og‘irlik (`500` gram, `1.2` kg).',
    )
    product_unit = ProductUnitChoiceField(
        required=False,
        allow_null=True,
        help_text='Birlik: `piece`, `gram`, `kg`, … Default — checkout dagi birlik (odatda `piece`).',
    )


class OrderPickingScanSerializer(serializers.Serializer):
    barcode = serializers.CharField(
        max_length=64,
        help_text='Mahsulot shtrixkodi (`ProductBarcode.barcode`). Qator `line_id` kerak emas.',
    )
    quantity = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=12,
        decimal_places=3,
        min_value=Decimal('0.001'),
        help_text='Yangi miqdor. Berilmasa — joriy `quantity` saqlanadi.',
    )
    product_unit = ProductUnitChoiceField(
        required=False,
        allow_null=True,
        help_text='`piece` = dona, `gram`/`kg` = tarozi. Default — checkout birligi.',
    )


def build_order_delivery_slot_payload(order: Order) -> Dict[str, Any]:
    da = order.delivery_address if getattr(order, 'delivery_address_id', None) else None
    return {
        'date': order.delivery_date.isoformat() if order.delivery_date else None,
        'time_start': _order_time_hhmm(order.delivery_time_start),
        'time_end': _order_time_hhmm(order.delivery_time_end),
        'delivery_slot_id': order.delivery_slot_id,
        'delivery_address_id': order.delivery_address_id,
        'saved_address': DeliveryAddressSerializer(da).data if da else None,
        'lat': str(order.lat) if order.lat is not None else None,
        'long': str(order.long) if order.long is not None else None,
        'address': order.address or None,
        'entrance': order.entrance or '',
        'apartment': order.apartment or '',
        'leave_at_door': bool(order.leave_at_door),
    }


class OrderListSerializer(serializers.ModelSerializer):
    """
    Optimized order serializer.
    Use with select_related and prefetch_related for best performance.
    """
    user_data = serializers.SerializerMethodField()
    order_pricing = serializers.SerializerMethodField()
    delivery_slot = serializers.SerializerMethodField()
    order_products = serializers.SerializerMethodField()
    order_couriers = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    can_user_cancel = serializers.SerializerMethodField()
    cancellation = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'user_data',
            'comment',
            'status',
            'status_display',
            'can_user_cancel',
            'cancellation',
            'order_pricing',
            'delivery_slot',
            'order_products',
            'order_couriers',
            'created_at',
            'updated_at',
        ]

    def get_can_user_cancel(self, obj) -> bool:
        return bool(getattr(obj, 'can_user_cancel', False))

    @extend_schema_field(OrderCancellationSerializer)
    def get_cancellation(self, obj) -> Optional[Dict[str, Any]]:
        return build_order_cancellation_payload(obj)

    def get_user_data(self, obj) -> Optional[Dict]:
        if obj.user:
            return UserMinSerializer(obj.user).data
        return None

    @extend_schema_field(OrderPricingSerializer)
    def get_order_pricing(self, obj) -> Dict[str, Any]:
        return build_order_pricing_payload(obj)

    @extend_schema_field(OrderDeliverySlotSerializer)
    def get_delivery_slot(self, obj) -> Dict[str, Any]:
        return build_order_delivery_slot_payload(obj)

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


class MyOrderListSerializer(OrderListSerializer):
    """
    Mijoz buyurtmalari — delivery QR (cash: to‘lov kutilmoqda; card: Click to‘langan).
    """

    cash_qr_code = serializers.SerializerMethodField()
    cash_qr_image_url = serializers.SerializerMethodField()

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + ['cash_qr_code', 'cash_qr_image_url']

    def _delivery_qr_visible(self, obj) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj.user_id != request.user.pk:
            return False
        from apps.orders.services.cash_delivery import delivery_qr_visible_for_customer

        return delivery_qr_visible_for_customer(obj)

    def get_cash_qr_code(self, obj) -> Optional[str]:
        if not self._delivery_qr_visible(obj):
            return None
        return obj.cash_qr_token

    def get_cash_qr_image_url(self, obj) -> Optional[str]:
        if not self._delivery_qr_visible(obj):
            return None
        from apps.orders.services.cash_delivery import ensure_cash_qr_image

        ensure_cash_qr_image(obj)
        if not obj.cash_qr_image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.cash_qr_image.url)
        return obj.cash_qr_image.url


class CashDeliveryConfirmSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    qr_code = serializers.CharField(max_length=64)


class CustomerDeliveryResponseSerializer(serializers.Serializer):
    """Mijoz: mahsulotni oldim / olmadim (cash, delivered)."""

    accepted = serializers.BooleanField(
        help_text='true — qabul qildim, false — rad etdim',
    )


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


class OrderClickPaymentSerializer(serializers.Serializer):
    return_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)


class OrderClickPaymentResponseSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    amount = serializers.CharField()
    merchant_trans_id = serializers.CharField()
    payment_url = serializers.URLField()


def _validate_cart_product_lines(value: List[Dict[str, Any]], *, check_min_order: bool) -> List[Dict[str, Any]]:
    if not value:
        raise serializers.ValidationError('Минимум один продукт')
    product_ids = [item['product_id'] for item in value]
    products = {
        p.id: p
        for p in Products.objects.filter(pk__in=product_ids, is_active=True, is_deleted=False)
    }
    missing = set(product_ids) - set(products.keys())
    if missing:
        raise serializers.ValidationError(f'Продукты не найдены: {", ".join(map(str, missing))}')
    from apps.orders.pricing import min_order_check

    sub = Decimal('0.00')
    unit_errors = []
    for item in value:
        p = products[item['product_id']]
        qty = Decimal(str(item['quantity']))
        req_unit = item.get('product_unit')
        try:
            line = compute_line_pricing(p, qty, product_unit=req_unit)
        except UnitPricingError as exc:
            unit_errors.append({
                'product_id': p.id,
                'detail': exc.message,
                'code': exc.code,
            })
            continue
        item['product_unit'] = line['product_unit']
        item['normalized_quantity'] = line['normalized_quantity']
        item['unit_price'] = line['unit_price']
        item['total_price'] = line['total_price']
        sub += line['total_price']
    if unit_errors:
        raise serializers.ValidationError({'products': unit_errors})
    if check_min_order:
        ok, threshold, shortfall = min_order_check(sub)
        if not ok:
            raise serializers.ValidationError(
                f'Минимальная сумма товаров {threshold} UZS. Не хватает {shortfall} UZS.'
            )
    return value


class PricingPreviewSerializer(serializers.Serializer):
    """POST body for cart pricing preview (no order persisted)."""
    products_data = serializers.ListField(
        child=OrderProductItemSerializer(),
        required=True,
        min_length=1,
    )
    delivery_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Дата доставки (как в GET /checkout/delivery-slots/ → `date`).',
    )
    delivery_time_start = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=8,
        help_text='Начало часового слота, напр. `09:00` (поле `start` из slots[]).',
    )
    delivery_time_end = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=8,
        help_text='Конец часового слота, напр. `10:00` (поле `end` из slots[]).',
    )
    loyalty_points_to_use = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text='Сколько баллов лояльности списать (не больше 50% суммы до скидки и баланса пользователя).',
    )

    def validate_products_data(self, value):
        return _validate_cart_product_lines(value, check_min_order=True)

    def validate(self, attrs):
        dd = attrs.get('delivery_date')
        ts = (attrs.get('delivery_time_start') or '').strip() if attrs.get('delivery_time_start') is not None else ''
        te = (attrs.get('delivery_time_end') or '').strip() if attrs.get('delivery_time_end') is not None else ''
        if not dd and not ts and not te:
            return attrs
        if dd is None or not ts or not te:
            raise serializers.ValidationError(
                'Поля delivery_date, delivery_time_start и delivery_time_end нужно передавать вместе.'
            )
        from apps.orders.busy_slot_schedule import parse_time_flexible, validate_delivery_window

        try:
            st = parse_time_flexible(ts)
            en = parse_time_flexible(te)
        except ValueError:
            raise serializers.ValidationError(
                {'delivery_time_start': 'Некорректное время. Формат HH:MM или HH-MM.'}
            )
        msg = validate_delivery_window(dd, st, en)
        if msg:
            raise serializers.ValidationError(msg)
        attrs['delivery_time_start'] = st
        attrs['delivery_time_end'] = en
        return attrs


class PricingPreviewResponseSerializer(serializers.Serializer):
    """Ответ POST /checkout/pricing-preview/ (все суммы — строки UZS, кроме флагов и баллов)."""
    products_subtotal = serializers.CharField()
    buffer_amount = serializers.CharField()
    service_fee_amount = serializers.CharField()
    packing_fee = serializers.CharField()
    delivery_fee = serializers.CharField()
    base_before_loyalty = serializers.CharField()
    loyalty_points_applied = serializers.IntegerField()
    loyalty_discount_amount = serializers.CharField()
    estimated_total = serializers.CharField()
    min_order_subtotal = serializers.CharField()
    min_order_met = serializers.BooleanField()
    amount_to_min_order = serializers.CharField()
    can_checkout = serializers.BooleanField()
    loyalty_max_money = serializers.CharField()


class DeliveryAddressSerializer(serializers.ModelSerializer):
    """User delivery addresses (Korzinka-style fields)."""

    class Meta:
        model = DeliveryAddress
        fields = [
            'id',
            'label',
            'street',
            'house_number',
            'apartment',
            'entrance',
            'floor',
            'intercom_code',
            'lat',
            'long',
            'is_default',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


# =============================================================================
# Fee Settings / Delivery Rules (Admin API)
# =============================================================================

class OrderFeeSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderFeeSettings
        fields = [
            'id',
            'service_fee_percent',
            'packing_fee_amount',
            'min_order_subtotal',
            'weight_buffer_percent',
            'loyalty_point_currency_value',
            'hourly_delivery_capacity',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']
        extra_kwargs = {
            'id': {'help_text': 'Идентификатор записи настроек (singleton, обычно `1`). Только чтение.'},
            'service_fee_percent': {
                'help_text': (
                    'Процент сервисного сбора от **суммы товаров** в заказе (без доставки и упаковки). '
                    'В расчёте: `service_fee_amount = products_subtotal × service_fee_percent / 100`.'
                ),
            },
            'packing_fee_amount': {
                'help_text': (
                    'Фиксированная сумма **упаковки** (один раз на заказ), добавляется к итогу '
                    'наряду с сервисом и доставкой.'
                ),
            },
            'min_order_subtotal': {
                'help_text': (
                    'Минимальная сумма **товаров** (`products_subtotal`) для успешного `POST /orders/` '
                    'и `can_checkout` в превью цены.'
                ),
            },
            'weight_buffer_percent': {
                'help_text': (
                    'Процент **буфера** от суммы строк с `sale_unit=weight` (закладывается в `buffer_amount`).'
                ),
            },
            'loyalty_point_currency_value': {
                'help_text': 'Сколько **UZS** эквивалентно **1 баллу** при списании (с ограничением 50% базы).',
            },
            'hourly_delivery_capacity': {
                'help_text': (
                    'Макс. **активных** заказов на один час (`GET /checkout/delivery-slots/` → `limit` в каждом слоте). '
                    'По умолчанию 15.'
                ),
            },
            'updated_at': {'help_text': 'Время последнего изменения (только чтение).'},
        }


class DeliveryFeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryFeeRule
        fields = ['id', 'min_order_amount', 'max_order_amount', 'fee_amount', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Идентификатор правила. Только чтение.'},
            'min_order_amount': {
                'help_text': (
                    'Нижняя граница суммы **товаров в заказе** (`products_subtotal`), с которой '
                    'действует это правило (включительно).'
                ),
            },
            'max_order_amount': {
                'help_text': (
                    'Верхняя граница той же суммы товаров (включительно). '
                    'Если **null** — верхней границы нет (интервал «от min и выше»).'
                ),
            },
            'fee_amount': {
                'help_text': (
                    'Сумма **доставки** для заказов, попавших в интервал '
                    '`min_order_amount ≤ subtotal ≤ max_order_amount` (при активном правиле).'
                ),
            },
            'is_active': {
                'help_text': (
                    'Неактивные правила в расчёте доставки не участвуют. '
                    'Правила перебираются по возрастанию `min_order_amount`; срабатывает **первое** подходящее.'
                ),
            },
            'created_at': {'help_text': 'Дата создания записи (только чтение).'},
        }
