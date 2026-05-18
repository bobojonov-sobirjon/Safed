from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db import models
from django.db.models import Sum
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.core.enums import UserGroup
from apps.products.models import Products, ProductBarcode
from apps.products.serializers import ProductListSerializer

from .models import Supplier, StockReceipt, StockReceiptItem, ReceiptStatus
from .serializers import (
    SupplierSerializer,
    StockReceiptSerializer,
    StockReceiptCreateSerializer,
    StockReceiptHeaderUpdateSerializer,
    ReceiptItemSerializer,
    ReceiptItemCreateUpdateSerializer,
    BarcodeLookupSerializer,
)


def user_is_admin(user) -> bool:
    return user.groups.filter(name__in=UserGroup.admin_groups()).exists()


class IsInventoryAdmin(BasePermission):
    """Доступ к inventory API: только Super Admin / Admin (как раньше в dispatch)."""

    message = 'Доступ запрещён'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return user_is_admin(user)


class AdminOnlyMixin:
    # Не возвращать Response из dispatch() — под ASGI не выставляется accepted_renderer.
    permission_classes = [IsInventoryAdmin]


# =============================================================================
# Suppliers
# =============================================================================

@extend_schema(
    tags=['Инвентаризация / Поставщики'],
    summary='Поставщики: список',
    description='Справочник поставщиков. Доступ: только группы **Super Admin** и **Admin**.',
)
class SupplierListCreateView(AdminOnlyMixin, APIView):
    def get(self, request):
        qs = Supplier.objects.all().order_by('-created_at')
        return Response(SupplierSerializer(qs, many=True).data)

    @extend_schema(
        request=SupplierSerializer,
        responses=SupplierSerializer,
        summary='Поставщики: создать',
        description='Создать нового поставщика. Доступ: только **Super Admin** и **Admin**.',
    )
    def post(self, request):
        serializer = SupplierSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        obj = serializer.save()
        return Response(SupplierSerializer(obj).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Инвентаризация / Поставщики'],
    summary='Поставщик: карточка',
    description='Получить поставщика по ID. Доступ: только **Super Admin** и **Admin**.',
)
class SupplierDetailView(AdminOnlyMixin, APIView):
    def get(self, request, pk):
        try:
            obj = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SupplierSerializer(obj).data)

    @extend_schema(
        request=SupplierSerializer,
        responses=SupplierSerializer,
        summary='Поставщик: обновить',
        description='Частичное обновление полей поставщика. Доступ: только **Super Admin** и **Admin**.',
    )
    def patch(self, request, pk):
        try:
            obj = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SupplierSerializer(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        summary='Поставщик: деактивировать (мягкое удаление)',
        description='Поставщик не удаляется физически: `is_active=false`. Доступ: только **Super Admin** и **Admin**.',
    )
    def delete(self, request, pk):
        try:
            obj = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['Инвентаризация / Поставщики'],
    summary='Акт сверки по поставщику',
    description='''Отчёт по поставщику: список приходных документов и суммы.

**Фильтры:**
- `date_from` / `date_to` — диапазон дат документа (`doc_date`).

**Доступ:** только **Super Admin** и **Admin**.''',
    parameters=[
        OpenApiParameter(name='date_from', type=OpenApiTypes.DATE, required=False, description='Дата от (YYYY-MM-DD)'),
        OpenApiParameter(name='date_to', type=OpenApiTypes.DATE, required=False, description='Дата до (YYYY-MM-DD)'),
    ],
)
class SupplierStatementView(AdminOnlyMixin, APIView):
    def get(self, request, pk):
        try:
            supplier = Supplier.objects.get(pk=pk)
        except Supplier.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        date_from = parse_date(request.query_params.get('date_from') or '') if request.query_params.get('date_from') else None
        date_to = parse_date(request.query_params.get('date_to') or '') if request.query_params.get('date_to') else None

        qs = StockReceipt.objects.filter(supplier=supplier).order_by('-doc_date', '-id')
        if date_from:
            qs = qs.filter(doc_date__gte=date_from)
        if date_to:
            qs = qs.filter(doc_date__lte=date_to)

        total = qs.aggregate(sum=Sum('subtotal')).get('sum') or 0
        return Response({
            'supplier': SupplierSerializer(supplier).data,
            'date_from': date_from.isoformat() if date_from else None,
            'date_to': date_to.isoformat() if date_to else None,
            'total_receipts': qs.count(),
            'total_amount': str(total),
            'receipts': StockReceiptSerializer(qs, many=True, context={'request': request}).data,
        })


# =============================================================================
# Receipts
# =============================================================================

@extend_schema(
    tags=['Инвентаризация / Приходы'],
    description='Приходные документы: список и создание черновика. Доступ: только **Super Admin** и **Admin**.',
)
class ReceiptListCreateView(AdminOnlyMixin, APIView):
    @extend_schema(
        summary='Приходы: список',
        description='Список приходных документов. Доступ: только **Super Admin** и **Admin**.',
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                required=False,
                description='Фильтр по статусу: `draft` / `posted` / `cancelled`.',
            ),
            OpenApiParameter(
                name='supplier',
                type=OpenApiTypes.INT,
                required=False,
                description='Фильтр по ID поставщика.',
            ),
        ],
    )
    def get(self, request):
        qs = StockReceipt.objects.select_related('supplier', 'created_by').order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        supplier_id = request.query_params.get('supplier')
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        return Response(StockReceiptSerializer(qs, many=True, context={'request': request}).data)

    @extend_schema(
        request=StockReceiptCreateSerializer,
        responses=StockReceiptSerializer,
        summary='Приходы: создать черновик (шапка документа)',
        description='''Создаёт приходный документ в статусе **черновик** (`draft`): шапка (дата, номер, поставщик).

Дальше добавляйте позиции через `POST /inventory/receipts/{id}/items/`, затем проведите документ через `POST /inventory/receipts/{id}/post/`.

Доступ: только **Super Admin** и **Admin**.''',
    )
    def post(self, request):
        serializer = StockReceiptCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        receipt = StockReceipt.objects.create(
            supplier_id=v['supplier_id'],
            doc_number=v['doc_number'],
            doc_date=v['doc_date'],
            status=ReceiptStatus.DRAFT,
            created_by=request.user,
        )
        return Response(StockReceiptSerializer(receipt, context={'request': request}).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Инвентаризация / Приходы'],
    summary='Приход: детали',
    description='Детали приходного документа вместе со строками (позициями). Доступ: только **Super Admin** и **Admin**.',
)
class ReceiptDetailView(AdminOnlyMixin, APIView):
    def get(self, request, pk):
        try:
            receipt = StockReceipt.objects.select_related('supplier', 'created_by').prefetch_related('items').get(pk=pk)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(StockReceiptSerializer(receipt, context={'request': request}).data)

    @extend_schema(
        request=StockReceiptHeaderUpdateSerializer,
        responses=StockReceiptSerializer,
        summary='Приход: обновить шапку (только черновик)',
        description='''Обновление шапки документа разрешено только в статусе **черновик** (`draft`).

Доступ: только **Super Admin** и **Admin**.''',
    )
    def patch(self, request, pk):
        try:
            receipt = StockReceipt.objects.get(pk=pk)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if receipt.status != ReceiptStatus.DRAFT:
            return Response({'detail': 'Изменение возможно только в статусе черновик (draft)'}, status=status.HTTP_400_BAD_REQUEST)
        # allow updating header fields
        for f in ['supplier', 'doc_number', 'doc_date', 'status']:
            if f in request.data:
                setattr(receipt, f, request.data.get(f))
        receipt.save()
        return Response(StockReceiptSerializer(receipt, context={'request': request}).data)


@extend_schema(
    tags=['Инвентаризация / Приходы'],
    summary='Приход: провести (увеличить остаток)',
    description='''Проводит приходный документ из **черновика** (`draft`) в **проведён** (`posted`).

**Эффект:**
- для каждой строки увеличивается `Products.quantity` на `quantity`
- документ блокируется (после проведения строки/шапку менять нельзя)

Операция выполняется в транзакции. Доступ: только **Super Admin** и **Admin**.''',
)
class ReceiptPostView(AdminOnlyMixin, APIView):
    @extend_schema(summary='Приход: провести')
    def post(self, request, pk):
        try:
            receipt = StockReceipt.objects.select_for_update().get(pk=pk)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if receipt.status != ReceiptStatus.DRAFT:
            return Response({'detail': 'Проведение возможно только из статуса черновик (draft)'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            items = list(receipt.items.select_related('product'))
            if not items:
                return Response({'detail': 'Документ пустой'}, status=status.HTTP_400_BAD_REQUEST)
            # increment stock
            for it in items:
                Products.objects.filter(pk=it.product_id).update(quantity=models.F('quantity') + it.quantity)
            receipt.status = ReceiptStatus.POSTED
            receipt.save(update_fields=['status', 'updated_at'])

        return Response(StockReceiptSerializer(receipt, context={'request': request}).data)


# =============================================================================
# Receipt items
# =============================================================================

@extend_schema(
    tags=['Инвентаризация / Позиции прихода'],
    summary='Позиции прихода: список',
    description='Список строк приходного документа. Доступ: только **Super Admin** и **Admin**.',
)
class ReceiptItemListCreateView(AdminOnlyMixin, APIView):
    def get(self, request, receipt_id):
        try:
            receipt = StockReceipt.objects.get(pk=receipt_id)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Документ не найден'}, status=status.HTTP_404_NOT_FOUND)
        qs = receipt.items.select_related('product').order_by('id')
        return Response(ReceiptItemSerializer(qs, many=True, context={'request': request}).data)

    @extend_schema(
        request=ReceiptItemCreateUpdateSerializer,
        responses=ReceiptItemSerializer,
        summary='Позиции прихода: добавить',
        description='''Добавляет строку в приходный документ (только **черновик**, `draft`).

**Цены:**
- можно передать `sell_price`
- или передать `margin_percent` — тогда `sell_price` рассчитается автоматически от `purchase_price`

Также сохраняются снимки (`product_name_snapshot`, `barcode_snapshot`) для истории.

Доступ: только **Super Admin** и **Admin**.''',
    )
    def post(self, request, receipt_id):
        try:
            receipt = StockReceipt.objects.get(pk=receipt_id)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Документ не найден'}, status=status.HTTP_404_NOT_FOUND)
        if receipt.status != ReceiptStatus.DRAFT:
            return Response({'detail': 'Добавление возможно только в статусе черновик (draft)'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ReceiptItemCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data

        product = Products.objects.get(pk=v['product_id'])
        purchase_price = v['purchase_price'].quantize(Decimal('0.01'))
        if 'sell_price' in v:
            sell_price = v['sell_price'].quantize(Decimal('0.01'))
            margin_percent = v.get('margin_percent')
        else:
            margin_percent = v['margin_percent']
            sell_price = (purchase_price * (Decimal('1.00') + (margin_percent / Decimal('100')))).quantize(Decimal('0.01'))

        line_total = (purchase_price * Decimal(v['quantity'])).quantize(Decimal('0.01'))
        barcode = ProductBarcode.objects.filter(product_id=product.id, is_deleted=False).values_list('barcode', flat=True).first() or ''

        item = StockReceiptItem.objects.create(
            receipt=receipt,
            product=product,
            quantity=v['quantity'],
            purchase_price=purchase_price,
            sell_price=sell_price,
            margin_percent=margin_percent,
            line_total=line_total,
            product_name_snapshot=product.safe_translation_getter('name', any_language=True) or '',
            barcode_snapshot=barcode,
        )

        # update receipt subtotal
        receipt.subtotal = receipt.items.aggregate(sum=Sum('line_total')).get('sum') or Decimal('0.00')
        receipt.save(update_fields=['subtotal', 'updated_at'])

        return Response(ReceiptItemSerializer(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Инвентаризация / Позиции прихода'],
    summary='Позиция прихода: изменить/удалить',
    description='Изменение/удаление строки разрешено только пока документ в статусе **черновик** (`draft`). Доступ: только **Super Admin** и **Admin**.',
)
class ReceiptItemDetailView(AdminOnlyMixin, APIView):
    @extend_schema(
        request=ReceiptItemCreateUpdateSerializer,
        responses=ReceiptItemSerializer,
        summary='Позиция прихода: обновить',
        description='Обновление строки (только **черновик**, `draft`). Доступ: только **Super Admin** и **Admin**.',
    )
    def patch(self, request, receipt_id, item_id):
        try:
            receipt = StockReceipt.objects.get(pk=receipt_id)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Документ не найден'}, status=status.HTTP_404_NOT_FOUND)
        if receipt.status != ReceiptStatus.DRAFT:
            return Response({'detail': 'Изменение возможно только в статусе черновик (draft)'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            item = StockReceiptItem.objects.select_related('product').get(pk=item_id, receipt_id=receipt_id)
        except StockReceiptItem.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReceiptItemCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data

        product = Products.objects.get(pk=v['product_id'])
        purchase_price = v['purchase_price'].quantize(Decimal('0.01'))
        if 'sell_price' in v:
            sell_price = v['sell_price'].quantize(Decimal('0.01'))
            margin_percent = v.get('margin_percent')
        else:
            margin_percent = v['margin_percent']
            sell_price = (purchase_price * (Decimal('1.00') + (margin_percent / Decimal('100')))).quantize(Decimal('0.01'))

        item.product = product
        item.quantity = v['quantity']
        item.purchase_price = purchase_price
        item.sell_price = sell_price
        item.margin_percent = margin_percent
        item.line_total = (purchase_price * Decimal(v['quantity'])).quantize(Decimal('0.01'))
        item.product_name_snapshot = product.safe_translation_getter('name', any_language=True) or ''
        item.barcode_snapshot = ProductBarcode.objects.filter(product_id=product.id, is_deleted=False).values_list('barcode', flat=True).first() or ''
        item.save()

        receipt.subtotal = receipt.items.aggregate(sum=Sum('line_total')).get('sum') or Decimal('0.00')
        receipt.save(update_fields=['subtotal', 'updated_at'])

        return Response(ReceiptItemSerializer(item, context={'request': request}).data)

    @extend_schema(
        summary='Позиция прихода: удалить',
        description='Удаление строки (только **черновик**, `draft`). Доступ: только **Super Admin** и **Admin**.',
    )
    def delete(self, request, receipt_id, item_id):
        try:
            receipt = StockReceipt.objects.get(pk=receipt_id)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Документ не найден'}, status=status.HTTP_404_NOT_FOUND)
        if receipt.status != ReceiptStatus.DRAFT:
            return Response({'detail': 'Удаление возможно только в статусе черновик (draft)'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            item = StockReceiptItem.objects.get(pk=item_id, receipt_id=receipt_id)
        except StockReceiptItem.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        receipt.subtotal = receipt.items.aggregate(sum=Sum('line_total')).get('sum') or Decimal('0.00')
        receipt.save(update_fields=['subtotal', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Barcode lookup
# =============================================================================

@extend_schema(
    tags=['Инвентаризация / Штрихкоды'],
    summary='Найти товар по штрихкоду',
    description='''Поиск товара по штрихкоду (для сканера).

**Параметр:** `barcode` (query).

**Ответ:** объект `product` (краткая карточка товара для списков).

Доступ: только **Super Admin** и **Admin**.''',
    parameters=[OpenApiParameter(name='barcode', type=OpenApiTypes.STR, required=True, description='Штрихкод')],
)
class ProductByBarcodeView(AdminOnlyMixin, APIView):
    def get(self, request):
        serializer = BarcodeLookupSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        barcode = serializer.validated_data['barcode']
        pb = ProductBarcode.objects.filter(barcode=barcode, is_deleted=False).select_related('product').first()
        if not pb or not pb.product:
            return Response({'detail': 'Товар не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'product': ProductListSerializer(pb.product, context={'request': request}).data})

