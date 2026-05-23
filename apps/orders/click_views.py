"""
CLICK payment: user payment URL + Prepare/Complete callbacks.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.enums import OrderStatus, PaymentStatus, PaymentType
from apps.orders.models import Order
from apps.orders.serializers import OrderClickPaymentResponseSerializer, OrderClickPaymentSerializer
from apps.orders.openapi_params import ORDER_PATH_PARAMS
from apps.orders.openapi_tags import TAG_PAYMENT
from apps.orders.services.click_payment import build_click_payment_url, handle_click_complete, handle_click_prepare

logger = logging.getLogger(__name__)


def _click_post_params(request) -> dict:
    if request.POST:
        return {k: request.POST.get(k) for k in request.POST}
    if isinstance(request.data, dict):
        return dict(request.data)
    return {}


@extend_schema(
    tags=[TAG_PAYMENT],
    summary='Ссылка на оплату CLICK (карта)',
    description="""
### Path: **`id`** — buyurtma ID (`POST /orders/` javobidagi `"id"`)

**`payment_type`: `card`**

1. **Birinchi to‘lov (checkout):** `status=created`, `payment_status=pending` — Click → `confirmed` + `paid` + **delivery QR** yaratiladi.

2. **Qo‘shimcha to‘lov (extra):** yig‘ishdan keyin `extra_payment_due` > 0 bo‘lsa — shu summa uchun yana Click. To‘langach kuryer QR skaner qiladi.

Возвращает **`payment_url`**. Опционально **`return_url`**.
""",
    parameters=ORDER_PATH_PARAMS,
    request=OrderClickPaymentSerializer,
    responses={200: OrderClickPaymentResponseSerializer},
)
class OrderClickPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ser = OrderClickPaymentSerializer(data=request.data or {})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(pk=pk, user=request.user, is_deleted=False)
        except Order.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_type != PaymentType.CARD.value:
            return Response(
                {'detail': 'Оплата CLICK только для payment_type=card'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.orders.services.cash_delivery import extra_payment_due

        if order.payment_status == PaymentStatus.PAID.value:
            amount = extra_payment_due(order)
            if amount <= 0:
                return Response(
                    {'detail': 'Qo‘shimcha to‘lov talab qilinmaydi', 'code': 'no_extra_due'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            payment_kind = 'extra'
        else:
            if order.status != OrderStatus.CREATED.value:
                return Response(
                    {'detail': 'Заказ не ожидает оплату'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            amount = order.estimated_total.quantize(Decimal('0.01'))
            payment_kind = 'checkout'

        if amount <= 0:
            return Response({'detail': 'Сумма заказа должна быть больше 0'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment_url = build_click_payment_url(
                order_id=order.pk,
                amount=amount,
                merchant_user_id=order.user_id,
                return_url=ser.validated_data.get('return_url'),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = {
            'order_id': order.pk,
            'amount': str(amount),
            'merchant_trans_id': str(order.pk),
            'payment_url': payment_url,
            'payment_kind': payment_kind,
        }
        return Response(payload)


@extend_schema(
    tags=[TAG_PAYMENT],
    summary='CLICK callback: Prepare',
    description='**CLICK server → sizning backend.** JWT kerak emas. Merchant kabinetda shu URL ni ko‘rsating.',
    request=None,
)
@method_decorator(csrf_exempt, name='dispatch')
class ClickPrepareView(APIView):
    """CLICK → merchant Prepare (action=0). Public, no JWT."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        params = _click_post_params(request)
        logger.info('CLICK prepare inbound order=%s trans=%s', params.get('merchant_trans_id'), params.get('click_trans_id'))
        return Response(handle_click_prepare(params))


@extend_schema(
    tags=[TAG_PAYMENT],
    summary='CLICK callback: Complete',
    description='**CLICK server → backend.** Muvaffaqiyatda buyurtma `confirmed` + `paid`. JWT kerak emas.',
    request=None,
)
@method_decorator(csrf_exempt, name='dispatch')
class ClickCompleteView(APIView):
    """CLICK → merchant Complete (action=1). Public, no JWT."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        params = _click_post_params(request)
        logger.info('CLICK complete inbound order=%s trans=%s err=%s', params.get('merchant_trans_id'), params.get('click_trans_id'), params.get('error'))
        return Response(handle_click_complete(params))
