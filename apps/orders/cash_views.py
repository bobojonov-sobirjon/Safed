"""Cash on delivery: courier QR confirm + QR image for customer."""
from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.enums import PaymentStatus, PaymentType
from apps.orders.cash_qr import render_cash_qr_png
from apps.orders.models import Order
from apps.orders.openapi_params import ORDER_PATH_PARAMS
from apps.orders.openapi_tags import TAG_COURIER, TAG_MY_ORDERS
from apps.orders.serializers import (
    CashDeliveryConfirmSerializer,
    CustomerDeliveryResponseSerializer,
    OrderListSerializer,
)
from apps.orders.services.cash_delivery import (
    CashDeliveryError,
    confirm_cash_delivery_by_qr,
    record_customer_delivery_response,
)
from apps.orders.views import user_is_courier


@extend_schema(
    tags=[TAG_MY_ORDERS],
    parameters=ORDER_PATH_PARAMS,
    summary='Cash QR rasm (PNG)',
    description="""
Faqat **buyurtma egasi**. `cash_qr_code` tokenini QR PNG qilib qaytaradi.

`GET /orders/my/` dagi **`cash_qr_image_url`** shu endpointga ishlatiladi.
Kuryer skaner qilganda ichidagi matn = `cash_qr_code`.
""",
    responses={200: {'content': {'image/png': {}}}},
)
class CashQrImageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user, is_deleted=False)
        if order.payment_type != PaymentType.CASH.value:
            return Response({'detail': 'Faqat cash buyurtma'}, status=status.HTTP_400_BAD_REQUEST)
        if order.payment_status != PaymentStatus.PENDING.value:
            return Response({'detail': 'QR faqat to‘lov kutilayotganda'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.orders.services.cash_delivery import ensure_cash_qr_image

        if not order.cash_qr_token:
            return Response({'detail': 'QR mavjud emas'}, status=status.HTTP_404_NOT_FOUND)

        ensure_cash_qr_image(order)
        if order.cash_qr_image:
            with order.cash_qr_image.open('rb') as fh:
                data = fh.read()
            response = HttpResponse(data, content_type='image/png')
            response['Cache-Control'] = 'private, max-age=3600'
            return response

        png = render_cash_qr_png(order.cash_qr_token)
        response = HttpResponse(png, content_type='image/png')
        response['Cache-Control'] = 'private, no-store'
        return response


@extend_schema(
    tags=[TAG_MY_ORDERS],
    parameters=ORDER_PATH_PARAMS,
    summary='Mahsulotni oldim / rad (REST)',
    description="""
Kuryer QR tasdiqlagach (`courier_confirmed_cash_payment` WS) mijoz javob beradi.

### Body
- **`accepted`**: `true` — oldim, `false` — olmadim / muammo

Xuddi WS: `{"action": "accept_delivery", "order_id": 8}`.

Kuryer ham WS da `customer_accept_delivery` / `customer_reject_delivery` oladi.
""",
    request=CustomerDeliveryResponseSerializer,
)
class CustomerDeliveryResponseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ser = CustomerDeliveryResponseSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, pk=pk, user=request.user, is_deleted=False)
        try:
            payload = record_customer_delivery_response(
                order=order,
                accepted=ser.validated_data['accepted'],
                user=request.user,
            )
        except CashDeliveryError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=[TAG_COURIER],
    summary='Cash: QR tasdiqlash (courier)',
    description="""
Faqat **Courier** va faqat o‘ziga biriktirilgan buyurtma.

### Body
- **`order_id`** — buyurtma ID
- **`qr_code`** — mijoz telefonidagi QR (`GET /orders/my/` → `cash_qr_code`)

### Natija (muvaffaqiyat)
- `payment_status` → **paid**
- `status` → **delivered**
- QR **bitta marta** — keyin invalidate
- Mijozga WebSocket: `courier_confirmed_cash_payment`

### Shartlar
- `payment_type=cash`, `payment_status=pending`, `status=shipped`
- `PATCH /status/` → `delivered` cash uchun **ishlamaydi**
""",
    request=CashDeliveryConfirmSerializer,
    responses={200: OrderListSerializer},
)
class CashDeliveryConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        if not user_is_courier(request.user):
            return Response({'detail': 'Faqat kuryer'}, status=status.HTTP_403_FORBIDDEN)

        ser = CashDeliveryConfirmSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            order, _summary = confirm_cash_delivery_by_qr(
                order_id=ser.validated_data['order_id'],
                qr_code=ser.validated_data['qr_code'],
                courier_user=request.user,
            )
        except CashDeliveryError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        order = (
            Order.objects.select_related('user')
            .prefetch_related('cancel_reasons')
            .get(pk=order.pk)
        )
        return Response(OrderListSerializer(order, context={'request': request}).data)
