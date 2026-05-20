"""WebSocket: cash delivery — bitta ulanish JWT bilan (order_id URL da emas)."""
from __future__ import annotations

import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.orders.services.cash_delivery import CashDeliveryError, record_customer_delivery_response
from apps.orders.services.delivery_events import courier_delivery_group, customer_delivery_group

logger = logging.getLogger(__name__)


class OrderDeliveryConsumer(AsyncWebsocketConsumer):
    """
    ws://host/ws/orders/delivery/token=<JWT>
    yoki ws://host/ws/orders/delivery/?token=<JWT>
    yoki ws://host/ws/orders/delivery/<JWT>/

    Server → mijoz (delivery WS):
    - courier_confirmed_cash_payment

    Mijoz javobi (accept/reject) → faqat Operator/Super Admin (`ws/notifications/`).

    Client → server (mijoz):
    - {"action": "accept_delivery", "order_id": 5}
    - {"action": "reject_delivery", "order_id": 5}
    """

    async def connect(self):
        self.user = self.scope.get('user')
        self.group_names: list[str] = []

        if not self.user or not getattr(self.user, 'is_authenticated', False):
            await self.close(code=4001)
            return

        self.is_courier = await self._user_is_courier()
        groups = [customer_delivery_group(self.user.pk)]
        if self.is_courier:
            groups.append(courier_delivery_group(self.user.pk))

        for name in groups:
            await self.channel_layer.group_add(name, self.channel_name)
            self.group_names.append(name)

        await self.accept()
        logger.info('WS delivery connected user=%s courier=%s', self.user.pk, self.is_courier)

        await self.send(text_data=json.dumps({
            'type': 'connected',
            'data': {
                'user_id': self.user.pk,
                'is_courier': self.is_courier,
            },
        }, ensure_ascii=False))

    async def disconnect(self, code):
        for name in getattr(self, 'group_names', []):
            await self.channel_layer.group_discard(name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            return

        action = (data.get('action') or '').strip()
        if action not in ('accept_delivery', 'reject_delivery'):
            return

        order_id_raw = data.get('order_id')
        if order_id_raw is None:
            await self._send_error('order_id kerak.', 'order_id')
            return

        try:
            order_id = int(order_id_raw)
        except (TypeError, ValueError):
            await self._send_error('order_id butun son.', 'order_id')
            return

        is_owner = await self._user_owns_order(order_id)
        if not is_owner:
            await self._send_error('Faqat buyurtma egasi accept/reject yubora oladi.', 'forbidden')
            return

        accepted = action == 'accept_delivery'
        await self._handle_customer_response(order_id, accepted)

    async def _user_is_courier(self) -> bool:
        @sync_to_async
        def check():
            from apps.orders.views import user_is_courier
            return user_is_courier(self.user)

        return await check()

    async def _user_owns_order(self, order_id: int) -> bool:
        @sync_to_async
        def check():
            from apps.orders.models import Order
            return Order.objects.filter(pk=order_id, user_id=self.user.pk, is_deleted=False).exists()

        return await check()

    async def _send_error(self, message: str, code: str) -> None:
        await self.send(text_data=json.dumps({
            'type': 'error',
            'data': {'message': message, 'code': code},
        }, ensure_ascii=False))

    async def _handle_customer_response(self, order_id: int, accepted: bool):
        @sync_to_async
        def apply():
            from apps.orders.models import Order

            order = Order.objects.get(pk=order_id, is_deleted=False)
            return record_customer_delivery_response(order=order, accepted=accepted, user=self.user)

        try:
            payload = await apply()
        except CashDeliveryError as exc:
            await self._send_error(exc.message, exc.code)
            return

        await self.send(text_data=json.dumps({
            'type': 'ack',
            'data': payload,
        }, ensure_ascii=False))

    async def delivery_event(self, event):
        await self.send(text_data=json.dumps({
            'type': event.get('event'),
            'data': event.get('data', {}),
        }, ensure_ascii=False))
