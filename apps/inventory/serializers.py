from __future__ import annotations

from decimal import Decimal
from typing import Optional, List, Dict, Any

from rest_framework import serializers

from .models import (
    Supplier,
    StockReceipt,
    StockReceiptItem,
    ReceiptStatus,
    SupplierReconciliationAct,
    ReconciliationActStatus,
)
from apps.products.models import Products, ProductBarcode
from apps.products.serializers import ProductListSerializer


_REQUIRED = {'required': 'Обязательное поле.'}


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'phone', 'contact_person', 'inn', 'address', 'is_active', 'created_at', 'updated_at']
        extra_kwargs = {
            'name': {'help_text': 'Название / ФИО поставщика.'},
            'phone': {'help_text': 'Телефон.'},
            'contact_person': {'help_text': 'Контактное лицо.'},
            'inn': {'help_text': 'ИНН / STIR.'},
            'address': {'help_text': 'Юридический или фактический адрес.'},
            'is_active': {'help_text': 'false — мягкое удаление, нельзя выбрать в новом приходе.'},
        }


class ReceiptItemSerializer(serializers.ModelSerializer):
    product_data = serializers.SerializerMethodField()

    class Meta:
        model = StockReceiptItem
        fields = [
            'id', 'product', 'product_data',
            'quantity', 'purchase_price', 'sell_price', 'margin_percent',
            'line_total', 'product_name_snapshot', 'barcode_snapshot',
            'created_at', 'updated_at',
        ]

    def get_product_data(self, obj) -> Optional[Dict[str, Any]]:
        if obj.product:
            return ProductListSerializer(obj.product, context=self.context).data
        return None


class StockReceiptSerializer(serializers.ModelSerializer):
    supplier_data = SupplierSerializer(source='supplier', read_only=True)
    items = ReceiptItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockReceipt
        fields = [
            'id', 'supplier', 'supplier_data',
            'doc_number', 'doc_date', 'status',
            'subtotal', 'created_by', 'posted_by', 'posted_at',
            'cancelled_by', 'cancelled_at',
            'created_at', 'updated_at',
            'items',
        ]
        read_only_fields = [
            'id', 'subtotal', 'created_by', 'posted_by', 'posted_at',
            'cancelled_by', 'cancelled_at', 'created_at', 'updated_at', 'items',
        ]


class StockReceiptHeaderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockReceipt
        fields = ['supplier', 'doc_number', 'doc_date']

    def validate_supplier(self, value):
        if not value.is_active:
            raise serializers.ValidationError('Поставщик неактивен.')
        return value


class StockReceiptCreateSerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField(
        required=True,
        help_text='ID поставщика (только активные).',
        error_messages=_REQUIRED,
    )
    doc_number = serializers.CharField(
        required=True,
        max_length=50,
        help_text='Номер приходного документа (уникальный в системе).',
        error_messages=_REQUIRED,
    )
    doc_date = serializers.DateField(required=True, help_text='Дата документа.', error_messages=_REQUIRED)

    def validate_supplier_id(self, value):
        if not Supplier.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Поставщик не найден')
        return value


class ReceiptItemCreateUpdateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(
        required=True,
        help_text='ID товара (не удалённый).',
        error_messages=_REQUIRED,
    )
    quantity = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text='Количество в строке прихода.',
        error_messages=_REQUIRED,
    )
    purchase_price = serializers.DecimalField(
        required=True,
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        help_text='Закупочная цена за единицу.',
    )
    sell_price = serializers.DecimalField(
        required=False,
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        help_text='Цена продажи за единицу (если не указана — будет рассчитана по наценке).',
    )
    margin_percent = serializers.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        min_value=Decimal('0.00'),
        help_text='Наценка в процентах от закупочной цены (если не указана `sell_price`).',
    )

    def validate_product_id(self, value):
        if not Products.objects.filter(pk=value, is_deleted=False).exists():
            raise serializers.ValidationError('Товар не найден')
        return value

    def validate(self, attrs):
        # If sell_price not provided but margin_percent provided → compute sell_price later in view/service.
        # If sell_price provided but margin_percent missing → ok.
        if 'sell_price' not in attrs and 'margin_percent' not in attrs:
            raise serializers.ValidationError(
                {'sell_price': 'Укажите цену продажи (sell_price) или наценку в процентах (margin_percent).'}
            )
        return attrs


class BarcodeLookupSerializer(serializers.Serializer):
    barcode = serializers.CharField(
        required=True,
        max_length=255,
        help_text='Штрихкод для поиска товара.',
        error_messages=_REQUIRED,
    )


class SupplierStatementSerializer(serializers.Serializer):
    supplier = SupplierSerializer()
    date_from = serializers.DateField(allow_null=True)
    date_to = serializers.DateField(allow_null=True)
    status_filter = serializers.CharField()
    opening_balance = serializers.CharField()
    total_receipts = serializers.IntegerField()
    total_amount = serializers.CharField()
    closing_balance = serializers.CharField()
    receipts = StockReceiptSerializer(many=True)


class SupplierReconciliationActSerializer(serializers.ModelSerializer):
    supplier_data = SupplierSerializer(source='supplier', read_only=True)

    class Meta:
        model = SupplierReconciliationAct
        fields = [
            'id',
            'supplier',
            'supplier_data',
            'period_from',
            'period_to',
            'opening_balance',
            'receipts_total',
            'receipts_count',
            'closing_balance',
            'status',
            'notes',
            'created_by',
            'confirmed_by',
            'confirmed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'receipts_total',
            'receipts_count',
            'closing_balance',
            'status',
            'confirmed_by',
            'confirmed_at',
            'created_at',
            'updated_at',
        ]


class SupplierReconciliationActCreateSerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField(required=True, error_messages=_REQUIRED)
    period_from = serializers.DateField(required=True, error_messages=_REQUIRED)
    period_to = serializers.DateField(required=True, error_messages=_REQUIRED)
    opening_balance = serializers.DecimalField(
        required=False,
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Долг поставщику на начало периода.',
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_supplier_id(self, value):
        if not Supplier.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Поставщик не найден или неактивен.')
        return value

    def validate(self, attrs):
        if attrs['period_to'] < attrs['period_from']:
            raise serializers.ValidationError({'period_to': 'Должно быть не раньше period_from.'})
        return attrs


class SupplierReconciliationActUpdateSerializer(serializers.Serializer):
    period_from = serializers.DateField(required=False)
    period_to = serializers.DateField(required=False)
    opening_balance = serializers.DecimalField(required=False, max_digits=14, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        period_from = attrs.get('period_from')
        period_to = attrs.get('period_to')
        if period_from and period_to and period_to < period_from:
            raise serializers.ValidationError({'period_to': 'Должно быть не раньше period_from.'})
        return attrs


class SupplierReconciliationActDetailSerializer(SupplierReconciliationActSerializer):
    receipts = StockReceiptSerializer(many=True, read_only=True)

    class Meta(SupplierReconciliationActSerializer.Meta):
        fields = SupplierReconciliationActSerializer.Meta.fields + ['receipts']


class ProductRestockSerializer(serializers.Serializer):
    barcode = serializers.CharField(
        required=True,
        max_length=255,
        help_text='Штрихкод товара для пополнения склада.',
        error_messages=_REQUIRED,
    )
    quantity = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text='Сколько единиц добавить к текущему остатку (`Products.quantity`).',
        error_messages=_REQUIRED,
    )

