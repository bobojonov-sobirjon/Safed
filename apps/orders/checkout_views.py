"""
Checkout: pricing preview, delivery slot availability, saved addresses.
Swagger tags: `01`–`03`, `06` — см. `openapi_tags.py`.
"""
from __future__ import annotations

from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, UserGroup
from apps.products.models import Products

from .models import BusyDayWorkingHours, DeliveryAddress, Order, OrderCancelReason
from .serializers import (
    PricingPreviewSerializer,
    PricingPreviewResponseSerializer,
    DeliveryAddressSerializer,
    DeliveryDaySetupSerializer,
    OrderListSerializer,
    OrderCancelReasonSerializer,
    OrderUserCancelSerializer,
)
from .pricing import build_pricing_preview
from .request_parsing import parse_order_request_data
from .slots import availability_payload, day_payload_for_date, parse_date_query
from .openapi_params import (
    ORDER_PATH_PARAMS,
    PARAM_ADDRESS_ID,
    PARAM_SLOT_DATE,
    PARAM_SLOT_RELATIVE,
)
from .openapi_descriptions import PRICING_PREVIEW_DESCRIPTION
from .openapi_tags import (
    TAG_ADDRESSES,
    TAG_DELIVERY_SLOTS,
    TAG_MY_ORDERS,
    TAG_PRICING_PREVIEW,
)


def user_is_admin(user) -> bool:
    return user.groups.filter(name__in=UserGroup.admin_groups()).exists()


@extend_schema(
    tags=[TAG_PRICING_PREVIEW],
    summary='Превью цены корзины',
    description=PRICING_PREVIEW_DESCRIPTION,
    request=PricingPreviewSerializer,
    responses={200: PricingPreviewResponseSerializer},
)
class OrderPricingPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import json

        try:
            body = parse_order_request_data(request.data)
        except (json.JSONDecodeError, ValueError) as exc:
            return Response({'products_data': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        ser = PricingPreviewSerializer(data=body)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        v = ser.validated_data
        ids = [i['product_id'] for i in v['products_data']]
        products = {p.id: p for p in Products.objects.filter(pk__in=ids, is_active=True, is_deleted=False)}

        preview = build_pricing_preview(
            products_data=v['products_data'],
            products_by_id=products,
            delivery_slot=None,
            loyalty_points_to_use=int(v.get('loyalty_points_to_use') or 0),
            user=request.user,
        )
        return Response(preview)


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_DELIVERY_SLOTS],
        summary='Слоты доставки: сетка на день',
        description="""
Почасовая сетка **автоматически** (отдельный POST на каждый час не нужен).

### Query (один из вариантов)
- **`relative`**: `today` | `tomorrow` (по умолчанию `today`)
- **`date`**: `YYYY-MM-DD` (конкретный день, для админа/календаря)

### Ответ
`date`, `working_hours`, `hourly_order_limit`, `slots[]` (`start`, `end`, `used`, `limit`, `available`, `disabled_reason`), опционально `tab`.

Слот закрыт только если **`full`** (лимит заказов) или **`cutoff`** (сегодня, < 30 мин до начала часа).

Мижоз заказ: `delivery_date` + `delivery_time_start` + `delivery_time_end` из выбранного `start`/`end`.
""",
        parameters=[PARAM_SLOT_RELATIVE, PARAM_SLOT_DATE],
    ),
    post=extend_schema(
        tags=[TAG_DELIVERY_SLOTS],
        summary='Админ: настроить день доставки (POST = busy-slots ham shu)',
        description="""
**Только Admin / Super Admin.** Bir xil endpoint: `/checkout/delivery-slots/` va `/busy-slots/`.

Kun uchun ish vaqti — shundan keyin `GET` da `slots[]` avtomatik chiqadi.

```json
[
  {"date": "2026-05-15", "start_time": "06:00", "end_time": "23:00"}
]
```
yoki `working_start` / `working_end` — bir xil.

Soat yopiladi faqat agar `used >= limit` (sozlama `hourly_delivery_capacity`).
""",
        request=DeliveryDaySetupSerializer(many=True),
    ),
)
class DeliverySlotAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        d = parse_date_query(request.query_params.get('date'))
        if d:
            return Response(availability_payload(on_date=d))
        rel = (request.query_params.get('relative') or 'today').lower()
        if rel not in ('today', 'tomorrow'):
            return Response({'relative': ['Must be today or tomorrow.']}, status=status.HTTP_400_BAD_REQUEST)
        return Response(availability_payload(rel))

    def post(self, request):
        if not user_is_admin(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        raw = request.data
        items = raw if isinstance(raw, list) else [raw]
        errors = []
        saved_dates = []
        for idx, item in enumerate(items):
            ser = DeliveryDaySetupSerializer(data=item)
            if not ser.is_valid():
                errors.append({'index': idx, 'errors': ser.errors})
                continue
            v = ser.validated_data
            BusyDayWorkingHours.objects.update_or_create(
                date=v['date'],
                defaults={
                    'working_start': v['working_start'],
                    'working_end': v['working_end'],
                },
            )
            saved_dates.append(v['date'])
        if errors:
            return Response({'detail': 'Validation failed', 'items': errors}, status=status.HTTP_400_BAD_REQUEST)
        out = [day_payload_for_date(d) for d in saved_dates]
        if len(out) == 1:
            return Response(out[0], status=status.HTTP_201_CREATED)
        return Response({'days': out}, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_ADDRESSES],
        summary='Список сохранённых адресов',
        description='Все адреса текущего пользователя: сначала **по умолчанию**, затем по `updated_at`.',
        responses=DeliveryAddressSerializer(many=True),
    ),
    post=extend_schema(
        tags=[TAG_ADDRESSES],
        summary='Создать адрес',
        description="""
Создаёт запись **`DeliveryAddress`**. Пользователь подставляется из токена.

Если в теле **`is_default`: true** — остальные адреса пользователя снимаются с флага по умолчанию.
""",
        request=DeliveryAddressSerializer,
        responses=DeliveryAddressSerializer,
    ),
)
class DeliveryAddressListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DeliveryAddress.objects.filter(user=request.user).order_by('-is_default', '-updated_at')
        return Response(DeliveryAddressSerializer(qs, many=True).data)

    def post(self, request):
        ser = DeliveryAddressSerializer(data=request.data, context={'request': request})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        obj = ser.save()
        if request.data.get('is_default'):
            DeliveryAddress.objects.filter(user=request.user).exclude(pk=obj.pk).update(is_default=False)
            obj.is_default = True
            obj.save(update_fields=['is_default'])
        return Response(DeliveryAddressSerializer(obj).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_ADDRESSES],
        parameters=[PARAM_ADDRESS_ID],
        summary='Адрес по ID',
        description='### Path: **`pk`** — manzil ID (`GET /addresses/` dan). Faqat o‘z manzili.',
        responses=DeliveryAddressSerializer,
    ),
    patch=extend_schema(
        tags=[TAG_ADDRESSES],
        parameters=[PARAM_ADDRESS_ID],
        summary='Обновить адрес',
        description='Частичное обновление полей. При **`is_default`: true** — снять default с остальных.',
        request=DeliveryAddressSerializer,
        responses=DeliveryAddressSerializer,
    ),
    delete=extend_schema(
        tags=[TAG_ADDRESSES],
        parameters=[PARAM_ADDRESS_ID],
        summary='Удалить адрес',
        description='### Path: **`pk`** — manzil ID. Javob **204**.',
        responses={204: OpenApiResponse(description='Адрес удалён')},
    ),
)
class DeliveryAddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        obj = get_object_or_404(DeliveryAddress, pk=pk, user=request.user)
        return Response(DeliveryAddressSerializer(obj).data)

    def patch(self, request, pk):
        obj = get_object_or_404(DeliveryAddress, pk=pk, user=request.user)
        ser = DeliveryAddressSerializer(obj, data=request.data, partial=True, context={'request': request})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        obj = ser.save()
        if request.data.get('is_default'):
            DeliveryAddress.objects.filter(user=request.user).exclude(pk=obj.pk).update(is_default=False)
            obj.is_default = True
            obj.save(update_fields=['is_default'])
        return Response(DeliveryAddressSerializer(obj).data)

    def delete(self, request, pk):
        obj = get_object_or_404(DeliveryAddress, pk=pk, user=request.user)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=[TAG_MY_ORDERS],
    summary='Sabablar ro‘yxati (bekor qilish)',
    description="""
Tayyor feedback sabablari — mijoz bir nechtasini tanlashi mumkin.

`name`: `{"uz": {"name": "..."}, "ru": {...}, "en": {...}}`
""",
    responses={200: OrderCancelReasonSerializer(many=True)},
)
class OrderCancelReasonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OrderCancelReason.objects.filter(is_active=True).order_by('sort_order', 'id')
        return Response(OrderCancelReasonSerializer(qs, many=True).data)


@extend_schema(
    tags=[TAG_MY_ORDERS],
    parameters=ORDER_PATH_PARAMS,
    summary='Отменить заказ (покупатель)',
    description="""
### Path: **`id`** — buyurtma ID

### Body (JSON yoki `multipart/form-data`)
- **`reason_ids`** — `[1, 3]` tayyor sabablar (`GET /orders/cancel-reasons/`). Bir nechta bo‘lishi mumkin.
- **`comment`** — erkin matn (ixtiyoriy).

**Kamida bittasi** kerak: `comment` (bo‘sh emas) yoki `reason_ids` (kamida 1 ta).

### Условия
Faqat buyurtma egasi. Faqat status **`created`**. `confirmed`, `picking`, `shipped`, `delivered` — **400**.

### Natija
Status **`cancelled`**, loyalty ball qaytariladi. Javobda **`cancellation`**: comment, reasons, `cancelled_at`.
""",
    request=OrderUserCancelSerializer,
    responses={200: OrderListSerializer},
)
class OrderUserCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.db.models import F

        order = get_object_or_404(Order, pk=pk, user=request.user, is_deleted=False)
        if not order.can_user_cancel:
            return Response(
                {'detail': 'Отмена доступна только при статусе created'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = OrderUserCancelSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        reason_ids = ser.validated_data['reason_ids']
        reasons = list(
            OrderCancelReason.objects.filter(pk__in=reason_ids, is_active=True).order_by('sort_order', 'id')
        )
        if len(reasons) != len(reason_ids):
            return Response(
                {'reason_ids': ['Недопустимый или неактивный ID причины']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = ser.validated_data['comment']
        now = timezone.now()
        with transaction.atomic():
            pts = int(order.loyalty_points_used or 0)
            if pts:
                CustomUser.objects.filter(pk=request.user.pk).update(loyalty_points=F('loyalty_points') + pts)
            order.status = OrderStatus.CANCELLED.value
            order.cancel_comment = comment
            order.cancelled_at = now
            order.save(update_fields=['status', 'cancel_comment', 'cancelled_at', 'updated_at'])
            order.cancel_reasons.set(reasons)

        order = Order.objects.prefetch_related('cancel_reasons').get(pk=order.pk)
        return Response(OrderListSerializer(order, context={'request': request}).data)
