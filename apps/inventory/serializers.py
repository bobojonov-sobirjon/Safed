from __future__ import annotations

from decimal import Decimal
from typing import Optional, List, Dict, Any

from rest_framework import serializers

from .models import Supplier, StockReceipt, StockReceiptItem, ReceiptStatus
from apps.products.models import Products, ProductBarcode
from apps.products.serializers import ProductListSerializer


_REQUIRED = {'required': 'Обязательное поле.'}


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'phone', 'contact_person', 'inn', 'address', 'is_active', 'created_at', 'updated_at']


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
            'subtotal', 'created_by', 'created_at', 'updated_at',
            'items',
        ]


class StockReceiptHeaderUpdateSerializer(serializers.Serializer):
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        required=False,
        help_text='ID поставщика.',
    )
    doc_number = serializers.CharField(required=False, max_length=50, help_text='Номер документа.')
    doc_date = serializers.DateField(required=False, help_text='Дата документа.')
    status = serializers.ChoiceField(
        choices=ReceiptStatus.choices,
        required=False,
        help_text='Статус документа. Обновление шапки через API допускается только для черновика (`draft`).',
    )


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

