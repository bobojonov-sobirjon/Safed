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
from apps.orders.views import user_is_operator_or_super_admin
from apps.products.models import Products, ProductBarcode
from apps.products.serializers import ProductListSerializer

from .models import (
    Supplier,
    StockReceipt,
    StockReceiptItem,
    ReceiptStatus,
    SupplierReconciliationAct,
    ReconciliationActStatus,
)
from .serializers import (
    SupplierSerializer,
    StockReceiptSerializer,
    StockReceiptCreateSerializer,
    StockReceiptHeaderUpdateSerializer,
    ReceiptItemSerializer,
    ReceiptItemCreateUpdateSerializer,
    BarcodeLookupSerializer,
    ProductRestockSerializer,
    SupplierReconciliationActSerializer,
    SupplierReconciliationActCreateSerializer,
    SupplierReconciliationActUpdateSerializer,
    SupplierReconciliationActDetailSerializer,
)
from .services.stock import StockError, restock_product_by_barcode
from .services.receipt import ReceiptError, post_stock_receipt, cancel_stock_receipt, recalculate_receipt_subtotal
from .services.reconciliation import (
    ReconciliationError,
    build_reconciliation_preview,
    confirm_reconciliation_act,
    posted_receipts_for_period,
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


class IsOperatorOrSuperAdmin(BasePermission):
    """Operator yoki Super Admin — sklad to‘ldirish va skaner."""

    message = 'Доступ запрещён'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return user_is_operator_or_super_admin(user)


class AdminOnlyMixin:
    # Не возвращать Response из dispatch() — под ASGI не выставляется accepted_renderer.
    permission_classes = [IsInventoryAdmin]


def _paginate_queryset(request, qs):
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
    except (TypeError, ValueError):
        return None, qs
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return {'limit': limit, 'offset': offset, 'count': qs.count()}, qs[offset:offset + limit]


# =============================================================================
# Suppliers
# =============================================================================

@extend_schema(
    tags=['Инвентаризация / Поставщики'],
    summary='Поставщики: список',
    description='Справочник поставщиков. Доступ: только группы **Super Admin** и **Admin**.',
)
class SupplierListCreateView(AdminOnlyMixin, APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter('is_active', OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
            OpenApiParameter('q', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, description='Поиск по name, phone, inn'),
            OpenApiParameter('limit', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter('offset', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
    )
    def get(self, request):
        qs = Supplier.objects.all().order_by('-created_at')
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=str(is_active).lower() in ('true', '1', 'yes'))
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                models.Q(name__icontains=q)
                | models.Q(phone__icontains=q)
                | models.Q(inn__icontains=q)
                | models.Q(contact_person__icontains=q)
            )
        meta, page = _paginate_queryset(request, qs)
        data = SupplierSerializer(page, many=True).data
        if meta:
            return Response({'count': meta['count'], 'limit': meta['limit'], 'offset': meta['offset'], 'results': data})
        return Response(data)

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
        OpenApiParameter(
            name='status',
            type=OpenApiTypes.STR,
            required=False,
            description='Фильтр статуса приходов. По умолчанию `posted`.',
        ),
        OpenApiParameter(
            name='opening_balance',
            type=OpenApiTypes.DECIMAL,
            required=False,
            description='Начальный долг поставщику на начало периода (для акта сверки).',
        ),
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
        status_filter = (request.query_params.get('status') or 'posted').strip()
        try:
            opening_balance = Decimal(str(request.query_params.get('opening_balance') or '0'))
        except Exception:
            opening_balance = Decimal('0.00')

        qs = StockReceipt.objects.filter(supplier=supplier).select_related('supplier', 'created_by').order_by('doc_date', 'id')
        if status_filter and status_filter != 'all':
            qs = qs.filter(status=status_filter)
        if date_from:
            qs = qs.filter(doc_date__gte=date_from)
        if date_to:
            qs = qs.filter(doc_date__lte=date_to)

        total = qs.aggregate(sum=Sum('subtotal')).get('sum') or Decimal('0.00')
        closing_balance = (opening_balance + total).quantize(Decimal('0.01'))
        return Response({
            'supplier': SupplierSerializer(supplier).data,
            'date_from': date_from.isoformat() if date_from else None,
            'date_to': date_to.isoformat() if date_to else None,
            'status_filter': status_filter,
            'opening_balance': str(opening_balance.quantize(Decimal('0.01'))),
            'total_receipts': qs.count(),
            'total_amount': str(total),
            'closing_balance': str(closing_balance),
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
            OpenApiParameter(name='date_from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='date_to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='limit', type=OpenApiTypes.INT, required=False),
            OpenApiParameter(name='offset', type=OpenApiTypes.INT, required=False),
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
        date_from = parse_date(request.query_params.get('date_from') or '') if request.query_params.get('date_from') else None
        date_to = parse_date(request.query_params.get('date_to') or '') if request.query_params.get('date_to') else None
        if date_from:
            qs = qs.filter(doc_date__gte=date_from)
        if date_to:
            qs = qs.filter(doc_date__lte=date_to)
        meta, page = _paginate_queryset(request, qs)
        data = StockReceiptSerializer(page, many=True, context={'request': request}).data
        if meta:
            return Response({'count': meta['count'], 'limit': meta['limit'], 'offset': meta['offset'], 'results': data})
        return Response(data)

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
        serializer = StockReceiptHeaderUpdateSerializer(receipt, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        receipt.refresh_from_db()
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
            receipt = StockReceipt.objects.get(pk=pk)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        try:
            with transaction.atomic():
                receipt = post_stock_receipt(receipt, posted_by=request.user)
        except ReceiptError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        receipt = StockReceipt.objects.select_related('supplier', 'created_by').prefetch_related('items').get(pk=receipt.pk)
        return Response(StockReceiptSerializer(receipt, context={'request': request}).data)


@extend_schema(
    tags=['Инвентаризация / Приходы'],
    summary='Приход: отменить',
    description='''Отмена прихода.

- **draft** → `cancelled` (без изменения остатков)
- **posted** → `cancelled` (остатки уменьшаются на количество строк)

Доступ: только **Super Admin** и **Admin**.''',
)
class ReceiptCancelView(AdminOnlyMixin, APIView):
    def post(self, request, pk):
        try:
            receipt = StockReceipt.objects.get(pk=pk)
        except StockReceipt.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        try:
            with transaction.atomic():
                receipt = cancel_stock_receipt(receipt, cancelled_by=request.user)
        except ReceiptError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        receipt = StockReceipt.objects.select_related('supplier', 'created_by').prefetch_related('items').get(pk=receipt.pk)
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

        recalculate_receipt_subtotal(receipt)

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

        recalculate_receipt_subtotal(receipt)

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
        recalculate_receipt_subtotal(receipt)
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


@extend_schema(
    tags=['Инвентаризация / Штрихкоды'],
    summary='Пополнить остаток по штрихкоду',
    description='''Быстрое пополнение склада по штрихкоду (сканер).

**Тело запроса:**
- `barcode` — штрихкод товара
- `quantity` — сколько добавить к текущему `Products.quantity`

**Пример:** было `10`, передали `quantity: 50` → станет `60`.

Доступ: **Operator** и **Super Admin**.''',
    request=ProductRestockSerializer,
)
class ProductRestockByBarcodeView(APIView):
    permission_classes = [IsOperatorOrSuperAdmin]

    def post(self, request):
        serializer = ProductRestockSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        try:
            product = restock_product_by_barcode(v['barcode'], v['quantity'])
        except StockError as exc:
            status_code = status.HTTP_404_NOT_FOUND if exc.code == 'not_found' else status.HTTP_400_BAD_REQUEST
            return Response({'detail': exc.message}, status=status_code)
        return Response(
            {
                'product': ProductListSerializer(product, context={'request': request}).data,
                'added_quantity': v['quantity'],
            },
            status=status.HTTP_200_OK,
        )


# =============================================================================
# Reconciliation acts (акт сверки)
# =============================================================================


@extend_schema(
    tags=['Инвентаризация / Акт сверки'],
    summary='Акты сверки: список / создать черновик',
)
class ReconciliationActListCreateView(AdminOnlyMixin, APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter('supplier', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter('status', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter('limit', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter('offset', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
    )
    def get(self, request):
        qs = SupplierReconciliationAct.objects.select_related('supplier').order_by('-created_at')
        supplier_id = request.query_params.get('supplier')
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        meta, page = _paginate_queryset(request, qs)
        data = SupplierReconciliationActSerializer(page, many=True).data
        if meta:
            return Response({'count': meta['count'], 'limit': meta['limit'], 'offset': meta['offset'], 'results': data})
        return Response(data)

    @extend_schema(
        request=SupplierReconciliationActCreateSerializer,
        responses=SupplierReconciliationActDetailSerializer,
        summary='Акт сверки: создать черновик',
        description='''Создаёт черновик акта сверки с поставщиком за период.

После создания можно просмотреть превью приходов. Подтверждение — `POST .../confirm/`.''',
    )
    def post(self, request):
        serializer = SupplierReconciliationActCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        supplier = Supplier.objects.get(pk=v['supplier_id'])
        preview = build_reconciliation_preview(
            supplier,
            period_from=v['period_from'],
            period_to=v['period_to'],
            opening_balance=v.get('opening_balance') or Decimal('0.00'),
        )
        act = SupplierReconciliationAct.objects.create(
            supplier=supplier,
            period_from=v['period_from'],
            period_to=v['period_to'],
            opening_balance=(v.get('opening_balance') or Decimal('0.00')).quantize(Decimal('0.01')),
            receipts_total=preview['receipts_total'],
            receipts_count=preview['receipts_count'],
            closing_balance=preview['closing_balance'],
            notes=v.get('notes') or '',
            created_by=request.user,
        )
        return Response(
            _reconciliation_act_detail_payload(act, preview['receipts'], request),
            status=status.HTTP_201_CREATED,
        )


def _reconciliation_act_detail_payload(act, receipts, request):
    data = SupplierReconciliationActDetailSerializer(act).data
    data['receipts'] = StockReceiptSerializer(receipts, many=True, context={'request': request}).data
    return data


@extend_schema(tags=['Инвентаризация / Акт сверки'])
class ReconciliationActDetailView(AdminOnlyMixin, APIView):
    @extend_schema(
        responses=SupplierReconciliationActDetailSerializer,
        summary='Акт сверки: детали',
    )
    def get(self, request, pk):
        try:
            act = SupplierReconciliationAct.objects.select_related('supplier').get(pk=pk)
        except SupplierReconciliationAct.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        receipts = list(posted_receipts_for_period(act.supplier_id, act.period_from, act.period_to))
        return Response(_reconciliation_act_detail_payload(act, receipts, request))

    @extend_schema(
        request=SupplierReconciliationActUpdateSerializer,
        responses=SupplierReconciliationActDetailSerializer,
        summary='Акт сверки: обновить черновик',
    )
    def patch(self, request, pk):
        try:
            act = SupplierReconciliationAct.objects.select_related('supplier').get(pk=pk)
        except SupplierReconciliationAct.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if act.status != ReconciliationActStatus.DRAFT:
            return Response({'detail': 'Изменение возможно только для черновика.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SupplierReconciliationActUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        for field in ('period_from', 'period_to', 'opening_balance', 'notes'):
            if field in v:
                setattr(act, field, v[field])
        preview = build_reconciliation_preview(
            act.supplier,
            period_from=act.period_from,
            period_to=act.period_to,
            opening_balance=act.opening_balance,
        )
        act.receipts_total = preview['receipts_total']
        act.receipts_count = preview['receipts_count']
        act.closing_balance = preview['closing_balance']
        act.save(
            update_fields=[
                'period_from', 'period_to', 'opening_balance', 'notes',
                'receipts_total', 'receipts_count', 'closing_balance', 'updated_at',
            ],
        )
        return Response(_reconciliation_act_detail_payload(act, preview['receipts'], request))

    @extend_schema(summary='Акт сверки: удалить черновик')
    def delete(self, request, pk):
        try:
            act = SupplierReconciliationAct.objects.get(pk=pk)
        except SupplierReconciliationAct.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if act.status != ReconciliationActStatus.DRAFT:
            return Response({'detail': 'Удаление возможно только для черновика.'}, status=status.HTTP_400_BAD_REQUEST)
        act.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['Инвентаризация / Акт сверки'],
    summary='Акт сверки: подтвердить',
    description='Фиксирует акт: пересчитывает суммы по **проведённым** приходам за период и блокирует редактирование.',
)
class ReconciliationActConfirmView(AdminOnlyMixin, APIView):
    def post(self, request, pk):
        try:
            act = SupplierReconciliationAct.objects.select_related('supplier').get(pk=pk)
        except SupplierReconciliationAct.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        try:
            with transaction.atomic():
                act = confirm_reconciliation_act(act, confirmed_by=request.user)
        except ReconciliationError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        receipts = list(posted_receipts_for_period(act.supplier_id, act.period_from, act.period_to))
        return Response(_reconciliation_act_detail_payload(act, receipts, request))

