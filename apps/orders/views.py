import json

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from django.db import transaction
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils.dateparse import parse_date
from datetime import date as date_cls, datetime as datetime_cls


def _period_to_iso(p):
    """Trunc* natijasi: datetime yoki date bo'lishi mumkin — JSON uchun YYYY-MM-DD."""
    if p is None:
        return None
    if isinstance(p, datetime_cls):
        return p.date().isoformat()
    if isinstance(p, date_cls):
        return p.isoformat()
    return str(p)

from .models import Order, OrderProduct, OrderCourier, DeliveryFeeRule, OrderFeeSettings, DeliveryAddress
from apps.products.models import Products
from .serializers import (
    OrderListSerializer,
    MyOrderListSerializer,
    OrderCreateSerializer,
    OrderUpdateSerializer,
    AddCourierSerializer,
    StatusChangeSerializer,
    OrderFeeSettingsSerializer,
    DeliveryFeeRuleSerializer,
)
from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, UserGroup, PaymentStatus, PaymentType, ProductUnit
from apps.products.unit_pricing import catalog_unit_for_product, stock_units_required
from .pricing import compute_order_pricing, build_pricing_preview, snapshot_order_checkout_total
from .openapi_params import (
    ORDER_PATH_PARAMS,
    PARAM_ADDRESS_ID,
    PARAM_DELIVERY_RULE_ID,
    PARAM_ORDER_STATUS_FILTER,
)
from .openapi_descriptions import ORDER_CREATE_DESCRIPTION
from .request_parsing import parse_order_request_data
from .openapi_tags import (
    TAG_ADMIN_OPERATIONS,
    TAG_COURIER,
    TAG_CREATE_ORDER,
    TAG_FEES,
    TAG_MY_ORDERS,
    TAG_ORDER_DETAIL,
    TAG_STATISTICS,
)
from decimal import Decimal

COURIER_GROUP = UserGroup.COURIER.value
STAFF_GROUPS = UserGroup.staff_groups()


def user_is_courier(user):
    return user.groups.filter(name=COURIER_GROUP).exists()


def user_is_staff(user):
    return user.groups.filter(name__in=STAFF_GROUPS).exists()


def user_is_super_admin(user):
    return user.groups.filter(name='Super Admin').exists()


def user_is_admin(user):
    return user.groups.filter(name__in=UserGroup.admin_groups()).exists()


def user_is_operator_or_super_admin(user):
    return user.groups.filter(
        name__in=[UserGroup.OPERATOR.value, UserGroup.SUPER_ADMIN.value],
    ).exists()


def finished_order_products_q():
    """Revenue / stats: cash completed yoki card delivered+paid."""
    return Q(order__status=OrderStatus.COMPLETED.value) | Q(
        order__status=OrderStatus.DELIVERED.value,
        order__payment_type=PaymentType.CARD.value,
        order__payment_status=PaymentStatus.PAID.value,
    )


def ensure_admin_or_super_admin(request):
    if not user_is_admin(request.user):
        return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
    return None


# ========== Create Order ==========

@extend_schema(
    tags=[TAG_CREATE_ORDER],
    summary='Создать заказ (checkout)',
    description=ORDER_CREATE_DESCRIPTION,
    request=OrderCreateSerializer,
    responses={201: OrderListSerializer},
)
class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            body = parse_order_request_data(request.data)
        except (json.JSONDecodeError, ValueError) as exc:
            return Response(
                {'products_data': [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = OrderCreateSerializer(data=body, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v = serializer.validated_data

        with transaction.atomic():
            user = CustomUser.objects.select_for_update().get(pk=request.user.pk)
            ids = [item['product_id'] for item in v['products_data']]
            products = {p.id: p for p in Products.objects.select_for_update().filter(id__in=ids)}
            insufficient = []
            for item in v['products_data']:
                p = products.get(item['product_id'])
                if not p:
                    continue
                needed = stock_units_required(p, item['normalized_quantity'])
                cat = catalog_unit_for_product(p)
                if cat == ProductUnit.PIECE.value:
                    if p.quantity < int(needed):
                        insufficient.append({
                            'product_id': p.id,
                            'available_quantity': p.quantity,
                            'requested_quantity': str(needed),
                        })
                elif Decimal(p.quantity) < needed:
                    insufficient.append({
                        'product_id': p.id,
                        'available_quantity': str(p.quantity),
                        'requested_quantity': str(needed),
                    })
            if insufficient:
                return Response(
                    {
                        'detail': 'Недостаточно товара на складе',
                        'products': insufficient,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            preview = build_pricing_preview(
                products_data=v['products_data'],
                products_by_id=products,
                delivery_slot=None,
                loyalty_points_to_use=int(v.get('loyalty_points_to_use') or 0),
                user=user,
            )
            pts_applied = int(preview['loyalty_points_applied'])
            if pts_applied > int(user.loyalty_points or 0):
                return Response({'loyalty_points_to_use': ['Недостаточно баллов.']}, status=status.HTTP_400_BAD_REQUEST)

            delivery_addr_obj = None
            if v.get('delivery_address_id'):
                da = DeliveryAddress.objects.get(pk=v['delivery_address_id'], user=request.user)
                lat, long = da.lat, da.long
                address = f'{da.street}, {da.house_number}'.strip().strip(',')
                entrance = (v.get('entrance') or da.entrance or '') or ''
                apartment = (v.get('apartment') or da.apartment or '') or ''
                delivery_addr_obj = da
            else:
                lat, long, address = v['lat'], v['long'], v['address']
                entrance = v.get('entrance') or ''
                apartment = v.get('apartment') or ''

            delivery_date = v.get('delivery_date')
            dts = v.get('delivery_time_start')
            dte = v.get('delivery_time_end')

            if pts_applied:
                CustomUser.objects.filter(pk=user.pk).update(loyalty_points=F('loyalty_points') - pts_applied)

            order = Order.objects.create(
                user=request.user,
                lat=lat,
                long=long,
                address=address,
                entrance=entrance or '',
                apartment=apartment or '',
                comment=v.get('comment') or '',
                status=OrderStatus.CREATED.value,
                payment_type=v['payment_type'],
                payment_status=PaymentStatus.PENDING.value,
                delivery_date=delivery_date,
                delivery_time_start=dts,
                delivery_time_end=dte,
                delivery_slot=None,
                delivery_address=delivery_addr_obj,
                loyalty_points_used=pts_applied,
                leave_at_door=bool(v.get('leave_at_door')),
            )
            for item in v['products_data']:
                qty = Decimal(str(item['quantity']))
                OrderProduct.objects.create(
                    order=order,
                    product_id=item['product_id'],
                    ordered_quantity=qty,
                    quantity=qty,
                    product_unit=item['product_unit'],
                    normalized_quantity=item['normalized_quantity'],
                    unit_price=item['unit_price'],
                    total_price=item['total_price'],
                )
            compute_order_pricing(order)
            snapshot_order_checkout_total(order)
            order.save()

            if order.payment_type == PaymentType.CASH.value:
                from .services.cash_delivery import assign_cash_qr_token
                assign_cash_qr_token(order)
                from apps.realtime.services.order_notifications import on_order_created_cash

                on_order_created_cash(order.pk)

        return Response(OrderListSerializer(order, context={'request': request}).data, status=status.HTTP_201_CREATED)


# ========== Add Courier ==========

@extend_schema(
    tags=[TAG_ADMIN_OPERATIONS],
    parameters=ORDER_PATH_PARAMS,
    summary='Назначить курьера',
    description="""
### Path: **`id`** — buyurtma ID (`Order.id`)

Назначает курьера заказу и переводит статус в **`shipped`**.

### Условия
- Заказ в статусе **`picking`**.
- Пользователь с `courier_id` — в группе **Courier**.

### Тело
- **`courier_id`** (integer) — ID пользователя-курьера.

### Ответ
Объект заказа (как в списке заказов).
""",
    request=AddCourierSerializer,
    responses={200: OrderListSerializer},
)
class OrderAddCourierView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = AddCourierSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        courier_id = serializer.validated_data['courier_id']

        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not order.can_add_courier:
            return Response({'detail': 'Курьера можно добавить только при статусе picking'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.models import CustomUser
        try:
            courier = CustomUser.objects.get(pk=courier_id)
        except CustomUser.DoesNotExist:
            return Response({'courier_id': ['Курьер не найден']}, status=status.HTTP_400_BAD_REQUEST)

        if not user_is_courier(courier):
            return Response({'courier_id': ['Пользователь не является курьером']}, status=status.HTTP_400_BAD_REQUEST)

        previous_status = order.status
        OrderCourier.objects.get_or_create(order=order, courier=courier)
        order.status = OrderStatus.SHIPPED.value
        order.save()

        from apps.realtime.services.order_notifications import on_courier_assigned, on_status_changed

        on_courier_assigned(order.pk, courier.pk)
        on_status_changed(order.pk, OrderStatus.SHIPPED.value, previous_status)

        return Response(OrderListSerializer(order, context={'request': request}).data)


# ========== Status Change ==========

@extend_schema(
    tags=[TAG_ADMIN_OPERATIONS],
    parameters=ORDER_PATH_PARAMS,
    summary='Сменить статус заказа',
    description="""
### Path: **`id`** — buyurtma ID (`Order.id`)

Изменяет статус заказа по **state machine** (только **персонал**).

### Переходы
- `created` → `confirmed`, `rejected`, `cancelled`
- `confirmed` → `picking`, `rejected`, `cancelled`
- `picking` → `shipped`, `rejected`, `cancelled`
- `shipped` → `delivered`, `rejected`
- `delivered` → faqat **cash QR** (`PATCH /orders/cash/confirm/`) → `completed`

### `delivered` (kuryer)
Kuryer manzilga yetdi. **Cash** da to‘lov hali emas — keyin QR confirm.

### `completed` (cash)
Faqat **`PATCH /orders/cash/confirm/`** orqali. To‘lov + ombor spisanie.

### Card
`delivered` — yakuniy (to‘lov allaqachon o‘tgan); ombor spisanie `delivered` da.

### Тело
- **`status`** — значение из enum в схеме.
""",
    request=StatusChangeSerializer,
    responses={200: OrderListSerializer},
)
class OrderStatusChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = StatusChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['status']

        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        if new_status == OrderStatus.COMPLETED.value:
            return Response(
                {
                    'detail': 'Status completed faqat PATCH /orders/cash/confirm/ (QR) orqali.',
                    'code': 'cash_use_qr_confirm',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not order.can_transition_to(new_status):
            return Response({'detail': 'Недопустимый переход статуса'}, status=status.HTTP_400_BAD_REQUEST)

        previous_status = order.status
        order.status = new_status

        if new_status == OrderStatus.DELIVERED.value:
            from django.utils import timezone

            if not order.delivered_at:
                order.delivered_at = timezone.now()
            if order.payment_type != PaymentType.CASH.value:
                from .pricing import compute_order_settlement

                compute_order_settlement(order)

        order.save()

        if (
            previous_status != OrderStatus.DELIVERED.value
            and new_status == OrderStatus.DELIVERED.value
            and order.payment_type != PaymentType.CASH.value
        ):
            from .services.cash_delivery import deduct_order_stock

            deduct_order_stock(order)

        from apps.realtime.services.order_notifications import on_status_changed

        on_status_changed(order.pk, new_status, previous_status)

        return Response(OrderListSerializer(order, context={'request': request}).data)


# ========== User Orders (my orders) ==========

@extend_schema(
    tags=[TAG_MY_ORDERS],
    summary='Мои заказы',
    description="""
Список заказов **текущего пользователя**, новые сверху.

### Query
- **`status`** (optional) — фильтр: `created`, `confirmed`, `picking`, `shipped`, `delivered`, `rejected`, `cancelled`.
""",
    parameters=[PARAM_ORDER_STATUS_FILTER],
)
class MyOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Order.objects.filter(user=request.user)
            .select_related('user')
            .prefetch_related('cancel_reasons')
            .order_by('-created_at')
        )
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(MyOrderListSerializer(qs, many=True, context={'request': request}).data)


# ========== All Orders (admin/staff) ==========

@extend_schema(
    tags=[TAG_ADMIN_OPERATIONS],
    summary='Все заказы (персонал)',
    description="""
Полный список заказов (только **staff**). Сортировка: новые сверху.

### Query
- **`status`** — фильтр по статусу.
- **`user`** — фильтр по ID покупателя.
""",
    parameters=[
        OpenApiParameter(name='status', type=OpenApiTypes.STR, description='Статус заказа (опционально).'),
        OpenApiParameter(name='user', type=OpenApiTypes.INT, description='ID пользователя-покупателя (опционально).'),
    ],
)
class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        qs = Order.objects.all().order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        user_id = request.query_params.get('user')
        if user_id:
            qs = qs.filter(user_id=user_id)

        return Response(OrderListSerializer(qs, many=True, context={'request': request}).data)


# ========== Courier: My assigned orders ==========

@extend_schema(
    tags=[TAG_COURIER],
    summary='Мои заказы (курьер)',
    description="""
Заказы, где текущий пользователь назначен курьером (`OrderCourier`).

### Query
- **`status`** — опциональный фильтр по статусу заказа.
""",
    parameters=[
        OpenApiParameter(
            name='status',
            type=OpenApiTypes.STR,
            description='Фильтр по статусу: created, confirmed, picking, shipped, delivered, rejected, cancelled.',
        ),
    ],
)
class CourierMyOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_courier(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        qs = Order.objects.filter(order_couriers__courier=request.user).order_by('-created_at').distinct()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(OrderListSerializer(qs, many=True, context={'request': request}).data)


@extend_schema(
    tags=[TAG_ADMIN_OPERATIONS],
    summary='Активные заказы',
    description="""
Заказы в «активных» статусах: **`created`**, **`confirmed`**, **`picking`**, **`shipped`** (ещё не финальные).

### Query
- **`status`** — дополнительный узкий фильтр внутри активных.
""",
    parameters=[
        OpenApiParameter(name='status', type=OpenApiTypes.STR, description='Опционально: статус из активных.'),
    ],
)
class ActiveOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        qs = Order.objects.filter(status__in=OrderStatus.active_statuses()).order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(OrderListSerializer(qs, many=True, context={'request': request}).data)


# ========== Order Detail, Update, Delete ==========

@extend_schema_view(
    get=extend_schema(
        tags=[TAG_ORDER_DETAIL],
        parameters=ORDER_PATH_PARAMS,
        summary='Buyurtma batafsil (GET)',
        description="""
### Path: **`id`** — buyurtma ID (`Order.id`)

Карточка заказа. Видит **владелец** или **персонал**.

### Muhim maydonlar javobda
- **`order_products[].id`** — yig‘ish uchun `line_id` (PATCH `/picking-lines/{line_id}/`)
- **`order_products[].product_id`** — katalog mahsulot ID
- `order_pricing`, `delivery_slot`, `status`, `cancellation` (agar `cancelled`)
""",
        responses={200: OrderListSerializer},
    ),
    put=extend_schema(
        tags=[TAG_ORDER_DETAIL],
        parameters=ORDER_PATH_PARAMS,
        summary='Обновить заказ',
        description="""
### Path: **`id`** — buyurtma ID

Частичное обновление заказа (владелец, только статус **`created`**).

### Можно передать
- **`products_data`** — полная замена строк заказа (старые удаляются). `quantity` — число (дробное для кг).
- Координаты, адрес, комментарий, слот / legacy время доставки, баллы — см. `OrderUpdateSerializer`.

### Ошибки
- **400** — не `created`, валидация, склад, цены, минимальный чек.
""",
        request=OrderUpdateSerializer,
        responses={200: OrderListSerializer},
    ),
    delete=extend_schema(
        tags=[TAG_ORDER_DETAIL],
        parameters=ORDER_PATH_PARAMS,
        summary='Удалить заказ',
        description="""
### Path: **`id`** — buyurtma ID

Жёсткое удаление записи заказа — **только** пока статус **`created`**.

Bekor qilish: **`POST /orders/<id>/cancel/`** — faqat **`created`** (sabablar: `GET /orders/cancel-reasons/`).
""",
    ),
)
class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not user_is_staff(request.user) and order.user != request.user:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        order = (
            Order.objects.select_related('user')
            .prefetch_related('cancel_reasons')
            .get(pk=order.pk)
        )

        if user_is_operator_or_super_admin(request.user) and order.user_id != request.user.pk:
            active = {
                OrderStatus.CONFIRMED.value,
                OrderStatus.PICKING.value,
                OrderStatus.SHIPPED.value,
                OrderStatus.CREATED.value,
            }
            if order.status in active:
                from apps.realtime.services.order_notifications import on_staff_viewed_order

                on_staff_viewed_order(order.pk, request.user.pk)

        return Response(OrderListSerializer(order, context={'request': request}).data)

    def put(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not order.can_update_or_delete:
            return Response({'detail': 'Обновление возможно только при статусе created'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            body = parse_order_request_data(request.data)
        except (json.JSONDecodeError, ValueError) as exc:
            return Response({'products_data': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderUpdateSerializer(
            data=body, partial=True, context={'order_id': order.pk, 'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data

        with transaction.atomic():
            if 'products_data' in v:
                ids = [item['product_id'] for item in v['products_data']]
                products = {p.id: p for p in Products.objects.select_for_update().filter(id__in=ids)}
                insufficient = []
                for item in v['products_data']:
                    p = products.get(item['product_id'])
                    if not p:
                        continue
                    needed = stock_units_required(p, item['normalized_quantity'])
                    cat = catalog_unit_for_product(p)
                    if cat == ProductUnit.PIECE.value:
                        if p.quantity < int(needed):
                            insufficient.append({
                                'product_id': p.id,
                                'available_quantity': p.quantity,
                                'requested_quantity': str(needed),
                            })
                    elif Decimal(p.quantity) < needed:
                        insufficient.append({
                            'product_id': p.id,
                            'available_quantity': str(p.quantity),
                            'requested_quantity': str(needed),
                        })
                if insufficient:
                    return Response(
                        {
                            'detail': 'Недостаточно товара на складе',
                            'products': insufficient,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if 'lat' in v:
                order.lat = v['lat']
            if 'long' in v:
                order.long = v['long']
            if 'address' in v:
                order.address = v['address']
            if 'entrance' in v:
                order.entrance = v['entrance'] or ''
            if 'apartment' in v:
                order.apartment = v['apartment'] or ''
            if 'comment' in v:
                order.comment = v['comment'] or ''
            if any(k in request.data for k in ('delivery_date', 'delivery_time_start', 'delivery_time_end')):
                order.delivery_date = v.get('delivery_date')
                order.delivery_time_start = v.get('delivery_time_start')
                order.delivery_time_end = v.get('delivery_time_end')
            if 'products_data' in v:
                order.order_products.all().delete()
                for item in v['products_data']:
                    qty = Decimal(str(item['quantity']))
                    OrderProduct.objects.create(
                        order=order,
                        product_id=item['product_id'],
                        ordered_quantity=qty,
                        quantity=qty,
                        product_unit=item['product_unit'],
                        normalized_quantity=item['normalized_quantity'],
                        unit_price=item['unit_price'],
                        total_price=item['total_price'],
                    )
            compute_order_pricing(order)
            order.save()

        return Response(OrderListSerializer(order, context={'request': request}).data)

    def delete(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not order.can_update_or_delete:
            return Response({'detail': 'Удаление возможно только при статусе created'}, status=status.HTTP_400_BAD_REQUEST)

        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== Statistika (Super Admin) ==========

@extend_schema(
    tags=[TAG_STATISTICS],
    summary='Общая статистика (Super Admin)',
    description='Количество заказов, выручка, клиенты, статусы. Поддерживает фильтрацию по дате и агрегацию по периодам.',
    parameters=[
        OpenApiParameter(name='date_from', type=OpenApiTypes.DATE, description='Дата от (YYYY-MM-DD)'),
        OpenApiParameter(name='date_to', type=OpenApiTypes.DATE, description='Дата до (YYYY-MM-DD)'),
        OpenApiParameter(
            name='period',
            type=OpenApiTypes.STR,
            description='Период агрегации для графиков: daily, weekly, monthly',
        ),
    ],
)
class StatsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_super_admin(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        period = (request.query_params.get('period') or 'daily').lower()
        date_from = parse_date(date_from_str) if date_from_str else None
        date_to = parse_date(date_to_str) if date_to_str else None

        orders_qs = Order.objects.all()
        if date_from:
            orders_qs = orders_qs.filter(created_at__date__gte=date_from)
        if date_to:
            orders_qs = orders_qs.filter(created_at__date__lte=date_to)

        total_orders = orders_qs.count()
        orders_by_status = list(
            orders_qs.values('status').annotate(count=Count('id')).order_by('status')
        )
        total_customers = orders_qs.values('user').distinct().count()

        revenue_qs = OrderProduct.objects.filter(finished_order_products_q())
        if date_from:
            revenue_qs = revenue_qs.filter(order__created_at__date__gte=date_from)
        if date_to:
            revenue_qs = revenue_qs.filter(order__created_at__date__lte=date_to)
        total_revenue = revenue_qs.aggregate(sum=Sum('total_price')).get('sum') or 0

        if period == 'weekly':
            trunc = TruncWeek('created_at')
        elif period == 'monthly':
            trunc = TruncMonth('created_at')
        else:
            trunc = TruncDate('created_at')

        orders_ts = list(
            orders_qs
            .annotate(period=trunc)
            .values('period')
            .annotate(orders_count=Count('id'))
            .order_by('period')
        )

        if period == 'weekly':
            trunc_rev = TruncWeek('order__created_at')
        elif period == 'monthly':
            trunc_rev = TruncMonth('order__created_at')
        else:
            trunc_rev = TruncDate('order__created_at')

        revenue_ts = list(
            revenue_qs
            .annotate(period=trunc_rev)
            .values('period')
            .annotate(revenue=Sum('total_price'))
            .order_by('period')
        )

        for item in orders_ts:
            if item['period'] is not None:
                item['period'] = _period_to_iso(item['period'])
        for item in revenue_ts:
            if item['period'] is not None:
                item['period'] = _period_to_iso(item['period'])

        return Response({
            'total_orders': total_orders,
            'total_customers': total_customers,
            'total_revenue': total_revenue,
            'orders_by_status': orders_by_status,
            'orders_timeseries': orders_ts,
            'revenue_timeseries': revenue_ts,
        })


@extend_schema(
    tags=[TAG_STATISTICS],
    summary='Статистика по продуктам (Super Admin)',
    description='Топ продаваемых продуктов и остатки на складе. Поддерживает фильтрацию по дате и категории.',
    parameters=[
        OpenApiParameter(name='date_from', type=OpenApiTypes.DATE, description='Дата от (YYYY-MM-DD)'),
        OpenApiParameter(name='date_to', type=OpenApiTypes.DATE, description='Дата до (YYYY-MM-DD)'),
        OpenApiParameter(name='category', type=OpenApiTypes.INT, description='ID категории продукта'),
        OpenApiParameter(
            name='period',
            type=OpenApiTypes.STR,
            description='Период агрегации для продаж: daily, weekly, monthly',
        ),
    ],
)
class ProductStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_super_admin(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        category_id = request.query_params.get('category')
        period = (request.query_params.get('period') or 'daily').lower()
        date_from = parse_date(date_from_str) if date_from_str else None
        date_to = parse_date(date_to_str) if date_to_str else None

        op_qs = OrderProduct.objects.filter(finished_order_products_q())
        if date_from:
            op_qs = op_qs.filter(order__created_at__date__gte=date_from)
        if date_to:
            op_qs = op_qs.filter(order__created_at__date__lte=date_to)
        if category_id:
            op_qs = op_qs.filter(product__category_id=category_id)

        top_products = list(
            op_qs.values('product_id')
            .annotate(
                total_quantity=Sum('quantity'),
                total_revenue=Sum('total_price'),
            )
            .order_by('-total_quantity')[:20]
        )

        products_qs = Products.objects.all()
        if category_id:
            products_qs = products_qs.filter(category_id=category_id)

        stock_total = products_qs.aggregate(
            total_products=Count('id'),
            total_quantity=Sum('quantity'),
        )
        low_stock = list(
            products_qs.filter(quantity__lte=5)
            .values('id', 'quantity')
            .order_by('quantity')[:50]
        )

        if period == 'weekly':
            trunc = TruncWeek('order__created_at')
        elif period == 'monthly':
            trunc = TruncMonth('order__created_at')
        else:
            trunc = TruncDate('order__created_at')

        sales_ts = list(
            op_qs
            .annotate(period=trunc)
            .values('period')
            .annotate(
                total_quantity=Sum('quantity'),
                total_revenue=Sum('total_price'),
            )
            .order_by('period')
        )
        for item in sales_ts:
            if item['period'] is not None:
                item['period'] = _period_to_iso(item['period'])

        return Response({
            'top_products': top_products,
            'stock': {
                'total_products': stock_total.get('total_products') or 0,
                'total_quantity': stock_total.get('total_quantity') or 0,
                'low_stock': low_stock,
            },
            'sales_timeseries': sales_ts,
        })


# =============================================================================
# Admin API: Fee settings & delivery rules (no Django admin required)
# =============================================================================

class OrderFeeSettingsView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(
        tags=[TAG_FEES],
        summary='Настройки сборов: получить',
        description='''**Назначение:** единая запись глобальных параметров сборов (singleton, обычно `id=1`).

**Что в ответе:**
- `service_fee_percent` — процент сервисного сбора от суммы товаров.
- `packing_fee_amount` — фиксированная упаковка на заказ.
- `min_order_subtotal` — минимальная сумма товаров для оформления заказа.
- `weight_buffer_percent` — процент буфера на весовые позиции (к пересчёту после взвешивания).
- `loyalty_point_currency_value` — сколько UZS даёт 1 балл при списании.
- `hourly_delivery_capacity` — макс. заказов на один час (`GET /checkout/delivery-slots/`, по умолчанию 15).
- `updated_at` — время последнего изменения.

**Как используется в заказе:** при расчёте заказа (`compute_order_pricing`) из суммы товаров считается сервис, к итогу добавляется упаковка и доставка по правилам из `/admin/fees/delivery-rules/`.

**Доступ:** только **Super Admin** или **Admin** (нужен действующий токен авторизации). Без прав — `403`.
''',
        responses=OrderFeeSettingsSerializer,
    )
    def get(self, request):
        denied = ensure_admin_or_super_admin(request)
        if denied:
            return denied
        obj, _ = OrderFeeSettings.objects.get_or_create(pk=1)
        return Response(OrderFeeSettingsSerializer(obj).data)

    @extend_schema(
        tags=[TAG_FEES],
        summary='Настройки сборов: обновить',
        description='''**Назначение:** частичное обновление (`PATCH`) полей глобальных сборов.

**Тело:** любое подмножество полей: `service_fee_percent`, `packing_fee_amount`, `min_order_subtotal`, `weight_buffer_percent`, `loyalty_point_currency_value`, `hourly_delivery_capacity`. Поля `id` и `updated_at` — только чтение.

**Эффект:** новые значения начнут участвовать в расчёте **следующих** заказов и пересчёте цен при вызове логики оформления заказа.

**Доступ:** только **Super Admin** или **Admin**. Ошибки валидации — `400`.
''',
        request=OrderFeeSettingsSerializer,
        responses=OrderFeeSettingsSerializer,
    )
    def patch(self, request):
        denied = ensure_admin_or_super_admin(request)
        if denied:
            return denied
        obj, _ = OrderFeeSettings.objects.get_or_create(pk=1)
        serializer = OrderFeeSettingsSerializer(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class DeliveryFeeRuleListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(
        tags=[TAG_FEES],
        summary='Правила доставки: список',
        description='''**Назначение:** получить все записи правил доставки (в т.ч. неактивные), отсортированные по `min_order_amount`, затем по `id`.

**Логика расчёта доставки** (как в `get_delivery_fee`):
- Берутся правила с `is_active=true` (при расчёте заказа; в этом списке вы видите все записи).
- Для суммы товаров заказа `products_subtotal` ищется **первое** правило, где `min_order_amount ≤ subtotal` и (`max_order_amount` пусто **или** `subtotal ≤ max_order_amount`).
- Тогда доставка = `fee_amount` выбранного правила; если ни одно не подошло — `0`.

**Доступ:** только **Super Admin** или **Admin** (`403` без прав).
''',
        responses=DeliveryFeeRuleSerializer(many=True),
    )
    def get(self, request):
        denied = ensure_admin_or_super_admin(request)
        if denied:
            return denied
        qs = DeliveryFeeRule.objects.all().order_by('min_order_amount', 'id')
        return Response(DeliveryFeeRuleSerializer(qs, many=True).data)

    @extend_schema(
        tags=[TAG_FEES],
        summary='Правила доставки: создать',
        description='''**Назначение:** добавить диапазон суммы заказа (по товарам) и соответствующую **фиксированную** сумму доставки.

**Обязательные поля в теле:** как минимум `min_order_amount`; остальные — по модели (см. подсказки полей в схеме).

**Рекомендации:**
- Диапазоны не должны пересекаться по смыслу для активных правил, иначе сработает **первое** по сортировке — проверяйте порядок `min_order_amount`.
- Для «от суммы и выше» оставьте `max_order_amount` пустым (`null`).

**Доступ:** только **Super Admin** или **Admin**. Успех — `201` с созданной записью.
''',
        request=DeliveryFeeRuleSerializer,
        responses=DeliveryFeeRuleSerializer,
    )
    def post(self, request):
        denied = ensure_admin_or_super_admin(request)
        if denied:
            return denied
        serializer = DeliveryFeeRuleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        obj = serializer.save()
        return Response(DeliveryFeeRuleSerializer(obj).data, status=status.HTTP_201_CREATED)


class DeliveryFeeRuleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[TAG_FEES],
        summary='Правило доставки: обновить',
        description='''**Назначение:** частично изменить правило по `id` (границы сумм, сумма доставки, флаг активности).

**Параметр пути:** `id` — первичный ключ записи `DeliveryFeeRule`.

**Доступ:** только **Super Admin** или **Admin**. Нет записи — `404`; ошибки валидации — `400`.
''',
        request=DeliveryFeeRuleSerializer,
        responses=DeliveryFeeRuleSerializer,
    )
    def patch(self, request, pk):
        denied = ensure_admin_or_super_admin(request)
        if denied:
            return denied
        try:
            obj = DeliveryFeeRule.objects.get(pk=pk)
        except DeliveryFeeRule.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DeliveryFeeRuleSerializer(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        tags=[TAG_FEES],
        summary='Правило доставки: удалить',
        description='''**Назначение:** безвозвратно удалить правило доставки по `id`.

**Внимание:** после удаления расчёт доставки для попадавших ранее в это правило сумм может перейти на другое правило или на ноль.

**Доступ:** только **Super Admin** или **Admin**. Нет записи — `404`. Успех — `204` без тела.
''',
        responses={204: OpenApiResponse(description='Правило удалено')},
    )
    def delete(self, request, pk):
        denied = ensure_admin_or_super_admin(request)
        if denied:
            return denied
        try:
            obj = DeliveryFeeRule.objects.get(pk=pk)
        except DeliveryFeeRule.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
