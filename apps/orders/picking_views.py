"""Staff APIs for order picking (weight/qty adjustment)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order, OrderProduct
from apps.orders.serializers import (
    OrderListSerializer,
    OrderPickingLineSerializer,
    OrderPickingScanSerializer,
    build_order_pricing_payload,
)
from apps.orders.services.picking import PickingError, apply_picking_by_barcode, apply_picking_quantity
from apps.orders.openapi_params import ORDER_LINE_PATH_PARAMS, ORDER_PATH_PARAMS
from apps.orders.openapi_descriptions import PICKING_LINE_DESCRIPTION, PICKING_SCAN_DESCRIPTION
from apps.orders.openapi_tags import TAG_PICKING
from apps.orders.views import user_is_staff


def _picking_response(request, order: Order, line_summary: dict) -> Response:
    return Response({
        'order': OrderListSerializer(order, context={'request': request}).data,
        'line': line_summary,
        'settlement': build_order_pricing_payload(order),
    })


@extend_schema(
    tags=[TAG_PICKING],
    summary='Yig‘ish: haqiqiy vazn/miqdor (qator bo‘yicha)',
    description=PICKING_LINE_DESCRIPTION + """
### Path parametrlar
| Parametr | Nima |
|----------|------|
| **`id`** | **Buyurtma ID** — `POST /orders/` yoki `GET /orders/active/` → `"id"` |
| **`line_id`** | **Buyurtma qatori ID** — `GET /orders/{id}/` → `order_products[].id`. **Bu `product_id` emas!** |

### Body
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `quantity` | decimal | **yes** | Haqiqiy miqdor: `2` dona, `1.250` kg, `500` gram |
| `product_unit` | string | no | `piece`, `kg`, `gram`, `liter`, `ml`. Default — checkout birligi |

### Javob `200`
`order`, `line` (yangilangan qator), `settlement` (qo‘shimcha to‘lov / qaytarish).

**Staff** (Operator/Admin). Status: **`confirmed`** yoki **`picking`**.
""",
    parameters=ORDER_LINE_PATH_PARAMS,
    request=OrderPickingLineSerializer,
)
class OrderPickingLineUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, line_id):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        ser = OrderPickingLineSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(pk=pk, is_deleted=False)
            order_product = OrderProduct.objects.get(pk=line_id, order_id=order.pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        except OrderProduct.DoesNotExist:
            return Response({'detail': 'Строка не найдена'}, status=status.HTTP_404_NOT_FOUND)

        try:
            qty = Decimal(str(ser.validated_data['quantity']))
        except (InvalidOperation, TypeError):
            return Response({'quantity': ['Некорректное число.']}, status=status.HTTP_400_BAD_REQUEST)

        pick_unit = ser.validated_data.get('product_unit')

        try:
            order, _, summary = apply_picking_quantity(
                order=order,
                order_product=order_product,
                quantity=qty,
                product_unit=pick_unit,
            )
        except PickingError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        from apps.realtime.services.order_notifications import on_picking_line

        on_picking_line(order.pk)

        return _picking_response(request, order, summary)


@extend_schema(
    tags=[TAG_PICKING],
    summary='Yig‘ish: shtrixkod (line_id kerak emas)',
    description=PICKING_SCAN_DESCRIPTION + """
### Path
- **`id`** — **buyurtma ID** (`Order.id`)

### Body
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `barcode` | string | **yes** | Mahsulot shtrixkodi (`ProductBarcode.barcode`) |
| `quantity` | decimal | no | Yangi miqdor. Berilmasa — joriy `quantity` saqlanadi |
| `product_unit` | string | no | `piece`, `gram`, `kg`, … Default — checkout birligi |

**Muhim:** `quantity: 2` dona → odatda `piece`. Tarozi: `{"quantity": "500", "product_unit": "gram"}`.

### Javob `200`
`order`, `line`, `settlement` — PATCH picking-lines bilan bir xil.

**Staff**. Status: **`confirmed`** yoki **`picking`**.
""",
    parameters=ORDER_PATH_PARAMS,
    request=OrderPickingScanSerializer,
)
class OrderPickingScanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        ser = OrderPickingScanSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(pk=pk, is_deleted=False)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        qty = None
        if ser.validated_data.get('quantity') is not None:
            try:
                qty = Decimal(str(ser.validated_data['quantity']))
            except (InvalidOperation, TypeError):
                return Response({'quantity': ['Некорректное число.']}, status=status.HTTP_400_BAD_REQUEST)

        pick_unit = ser.validated_data.get('product_unit')

        try:
            order, _, summary = apply_picking_by_barcode(
                order=order,
                barcode=ser.validated_data['barcode'],
                quantity=qty,
                product_unit=pick_unit,
            )
        except PickingError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        from apps.realtime.services.order_notifications import on_picking_scan

        on_picking_scan(order.pk)

        return _picking_response(request, order, summary)
