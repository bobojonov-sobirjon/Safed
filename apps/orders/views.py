from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from django.db import transaction
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils.dateparse import parse_date

from .models import Order, OrderProduct, OrderCourier
from apps.products.models import Products
from .serializers import (
    OrderListSerializer,
    OrderCreateSerializer,
    OrderUpdateSerializer,
    AddCourierSerializer,
    StatusChangeSerializer,
)

COURIER_GROUP = 'Courier'
STAFF_GROUPS = ['Super Admin', 'Admin', 'Operator', 'Courier']


def user_is_courier(user):
    return user.groups.filter(name=COURIER_GROUP).exists()


def user_is_staff(user):
    return user.groups.filter(name__in=STAFF_GROUPS).exists()


def user_is_super_admin(user):
    return user.groups.filter(name='Super Admin').exists()


# ========== Create Order ==========

@extend_schema(
    tags=['Заказы'],
    summary='Создать заказ',
    description='''Создание нового заказа.

**Поля:**
- `products_data` - список продуктов (обязательно)
- `lat` - широта (опционально)
- `long` - долгота (опционально)
- `address` - адрес доставки (опционально)

**Примечание:** Статус заказа автоматически устанавливается как `pending`.
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'products_data': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'product_id': {'type': 'integer', 'description': 'ID продукта', 'example': 1},
                            'quantity': {'type': 'integer', 'description': 'Количество', 'example': 2},
                            'total_price': {'type': 'number', 'description': 'Общая цена', 'example': 30000.00},
                        },
                        'required': ['product_id', 'quantity', 'total_price'],
                    },
                    'description': 'Список продуктов',
                    'example': [
                        {'product_id': 1, 'quantity': 2, 'total_price': 30000.00},
                        {'product_id': 3, 'quantity': 1, 'total_price': 15000.00},
                    ],
                },
                'lat': {'type': 'number', 'description': 'Широта', 'example': 41.311081},
                'long': {'type': 'number', 'description': 'Долгота', 'example': 69.240562},
                'address': {'type': 'string', 'description': 'Адрес доставки', 'example': 'г. Ташкент, ул. Амира Темура, 10'},
            },
            'required': ['products_data'],
        }
    },
)
class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v = serializer.validated_data

        with transaction.atomic():
            ids = [item['product_id'] for item in v['products_data']]
            products = {p.id: p for p in Products.objects.select_for_update().filter(id__in=ids)}
            insufficient = []
            for item in v['products_data']:
                p = products.get(item['product_id'])
                if not p:
                    continue
                if p.quantity < item['quantity']:
                    insufficient.append({
                        'product_id': p.id,
                        'available_quantity': p.quantity,
                        'requested_quantity': item['quantity'],
                    })
            if insufficient:
                return Response(
                    {
                        'detail': 'Недостаточно товара на складе',
                        'products': insufficient,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.create(
                user=request.user,
                lat=v.get('lat'),
                long=v.get('long'),
                address=v.get('address', ''),
                status='pending',
            )
            for item in v['products_data']:
                OrderProduct.objects.create(
                    order=order,
                    product_id=item['product_id'],
                    quantity=item['quantity'],
                    total_price=item['total_price'],
                )

        return Response(OrderListSerializer(order, context={'request': request}).data, status=status.HTTP_201_CREATED)


# ========== Add Courier ==========

@extend_schema(
    tags=['Заказы'],
    summary='Добавить курьера',
    description='''Назначить курьера на заказ.

**Условия:**
- Заказ должен быть в статусе `pending`
- После назначения статус меняется на `delivering`
- Пользователь должен быть в группе `Courier`
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'courier_id': {'type': 'integer', 'description': 'ID курьера', 'example': 5},
            },
            'required': ['courier_id'],
        }
    },
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
            return Response({'detail': 'Курьера можно добавить только при статусе pending'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.models import CustomUser
        try:
            courier = CustomUser.objects.get(pk=courier_id)
        except CustomUser.DoesNotExist:
            return Response({'courier_id': ['Курьер не найден']}, status=status.HTTP_400_BAD_REQUEST)

        if not user_is_courier(courier):
            return Response({'courier_id': ['Пользователь не является курьером']}, status=status.HTTP_400_BAD_REQUEST)

        OrderCourier.objects.get_or_create(order=order, courier=courier)
        order.status = 'delivering'
        order.save()

        return Response(OrderListSerializer(order, context={'request': request}).data)


# ========== Status Change ==========

@extend_schema(
    tags=['Заказы'],
    summary='Изменить статус',
    description='''Изменить статус заказа.

**Доступные статусы:**
- `pending` - Ожидает обработки
- `process` - В обработке
- `delivering` - Доставляется
- `completed` - Завершён
- `rejected` - Отклонён

**Примечание:** При переходе в статус `completed` автоматически уменьшается количество товаров на складе.
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'status': {
                    'type': 'string',
                    'enum': ['pending', 'process', 'delivering', 'completed', 'rejected'],
                    'description': 'Новый статус заказа',
                    'example': 'delivering'
                },
            },
            'required': ['status'],
        }
    },
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

        previous_status = order.status
        order.status = new_status
        order.save()

        if previous_status != 'completed' and new_status == 'completed':
            products_qs = OrderProduct.objects.select_related('product').filter(order=order)
            for op in products_qs:
                if op.product:
                    Products.objects.filter(id=op.product_id).update(
                        quantity=F('quantity') - op.quantity
                    )

        return Response(OrderListSerializer(order, context={'request': request}).data)


# ========== User Orders (my orders) ==========

@extend_schema(
    tags=['Заказы'],
    summary='Мои заказы',
    parameters=[
        OpenApiParameter(name='status', type=OpenApiTypes.STR, description='pending, process, delivering, completed, rejected'),
    ],
)
class MyOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Order.objects.filter(user=request.user).order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(OrderListSerializer(qs, many=True, context={'request': request}).data)


# ========== All Orders (admin/staff) ==========

@extend_schema(
    tags=['Заказы'],
    summary='Все заказы',
    parameters=[
        OpenApiParameter(name='status', type=OpenApiTypes.STR),
        OpenApiParameter(name='user', type=OpenApiTypes.INT, description='ID пользователя'),
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


# ========== Order Detail, Update, Delete ==========

@extend_schema_view(
    get=extend_schema(tags=['Заказы'], summary='Заказ по ID'),
    put=extend_schema(
        tags=['Заказы'],
        summary='Обновить заказ',
        description='''Обновление заказа. Все поля опциональны.

**Условия:**
- Обновление возможно только при статусе `pending`
- При изменении `products_data` старые продукты удаляются
''',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'products_data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'product_id': {'type': 'integer', 'example': 1},
                                'quantity': {'type': 'integer', 'example': 3},
                                'total_price': {'type': 'number', 'example': 45000.00},
                            },
                        },
                        'example': [{'product_id': 1, 'quantity': 3, 'total_price': 45000.00}],
                    },
                    'lat': {'type': 'number', 'example': 41.311081},
                    'long': {'type': 'number', 'example': 69.240562},
                    'address': {'type': 'string', 'example': 'г. Ташкент, ул. Навои, 25'},
                },
            }
        },
    ),
    delete=extend_schema(
        tags=['Заказы'],
        summary='Удалить заказ',
        description='Удаление возможно только при статусе `pending`.',
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

        return Response(OrderListSerializer(order, context={'request': request}).data)

    def put(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not order.can_update_or_delete:
            return Response({'detail': 'Обновление возможно только при статусе pending'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderUpdateSerializer(data=request.data, partial=True)
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
                    if p.quantity < item['quantity']:
                        insufficient.append({
                            'product_id': p.id,
                            'available_quantity': p.quantity,
                            'requested_quantity': item['quantity'],
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
            if 'products_data' in v:
                order.order_products.all().delete()
                for item in v['products_data']:
                    OrderProduct.objects.create(
                        order=order,
                        product_id=item['product_id'],
                        quantity=item['quantity'],
                        total_price=item['total_price'],
                    )
            order.save()

        return Response(OrderListSerializer(order, context={'request': request}).data)

    def delete(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not order.can_update_or_delete:
            return Response({'detail': 'Удаление возможно только при статусе pending'}, status=status.HTTP_400_BAD_REQUEST)

        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== Statistika (Super Admin) ==========

@extend_schema(
    tags=['Статистика'],
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

        revenue_qs = OrderProduct.objects.filter(order__status='completed')
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
                item['period'] = item['period'].date().isoformat()
        for item in revenue_ts:
            if item['period'] is not None:
                item['period'] = item['period'].date().isoformat()

        return Response({
            'total_orders': total_orders,
            'total_customers': total_customers,
            'total_revenue': total_revenue,
            'orders_by_status': orders_by_status,
            'orders_timeseries': orders_ts,
            'revenue_timeseries': revenue_ts,
        })


@extend_schema(
    tags=['Статистика'],
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

        op_qs = OrderProduct.objects.filter(order__status='completed')
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
                item['period'] = item['period'].date().isoformat()

        return Response({
            'top_products': top_products,
            'stock': {
                'total_products': stock_total.get('total_products') or 0,
                'total_quantity': stock_total.get('total_quantity') or 0,
                'low_stock': low_stock,
            },
            'sales_timeseries': sales_ts,
        })
