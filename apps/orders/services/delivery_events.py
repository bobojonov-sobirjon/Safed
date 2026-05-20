"""Realtime delivery confirmation events (Django Channels)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

EVENT_COURIER_CONFIRMED = 'courier_confirmed_cash_payment'
EVENT_CUSTOMER_ACCEPT = 'customer_accept_delivery'
EVENT_CUSTOMER_REJECT = 'customer_reject_delivery'


def customer_delivery_group(user_id: int) -> str:
    return f'delivery_customer_{user_id}'


def courier_delivery_group(user_id: int) -> str:
    return f'delivery_courier_{user_id}'


def _recipient_groups_for_order(
    order_id: int,
    *,
    include_customer: bool = True,
    include_couriers: bool = True,
) -> List[str]:
    from apps.orders.models import Order, OrderCourier

    groups: List[str] = []
    try:
        order = Order.objects.only('user_id').get(pk=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return groups

    if include_customer:
        groups.append(customer_delivery_group(order.user_id))
    if include_couriers:
        courier_ids = OrderCourier.objects.filter(order_id=order_id).values_list(
            'courier_id', flat=True,
        )
        for cid in courier_ids:
            groups.append(courier_delivery_group(cid))
    return groups


def broadcast_order_delivery_event(
    *,
    order_id: int,
    event: str,
    data: Dict[str, Any],
    include_customer: bool = True,
    include_couriers: bool = True,
) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning('No channel layer; skip delivery event %s order=%s', event, order_id)
        return

    payload = {
        'type': 'delivery_event',
        'event': event,
        'data': {**data, 'order_id': order_id},
    }
    seen = set()
    for group in _recipient_groups_for_order(
        order_id,
        include_customer=include_customer,
        include_couriers=include_couriers,
    ):
        if group in seen:
            continue
        seen.add(group)
        async_to_sync(channel_layer.group_send)(group, payload)
    logger.info('Delivery WS event=%s order_id=%s groups=%s', event, order_id, len(seen))
