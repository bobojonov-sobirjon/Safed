"""Persist notification, WebSocket (`notif_{user_id}`), and optional FCM push."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model

from apps.accounts.models import UserDevice
from apps.realtime.models import Notification
from apps.realtime.services.fcm import send_fcm_to_tokens

logger = logging.getLogger(__name__)
User = get_user_model()


def _serialize_notification(notif: Notification) -> Dict[str, Any]:
    return {
        'id': notif.id,
        'title': notif.title,
        'body': notif.body,
        'type': notif.type,
        'data': notif.data,
        'is_read': notif.is_read,
        'created_at': notif.created_at.isoformat(),
    }


def _push_ws(user_id: int, payload: Dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f'notif_{user_id}',
        {'type': 'notification_message', 'data': payload},
    )


def _push_fcm(user_id: int, *, title: str, body: str, data: Dict[str, Any]) -> None:
    tokens = list(
        UserDevice.objects.filter(user_id=user_id, is_active=True).values_list(
            'device_token', flat=True,
        ),
    )
    if not tokens:
        return
    fcm_data = {k: str(v) for k, v in data.items()}
    fcm_data.setdefault('title', title)
    fcm_data.setdefault('body', body)
    send_fcm_to_tokens(tokens, title=title, body=body, data=fcm_data)


def notify_user(
    user_id: int,
    *,
    title: str,
    body: str,
    notif_type: str = '',
    data: Optional[Dict[str, Any]] = None,
    send_push: bool = True,
) -> Notification:
    """Create DB row, WS event, and FCM for one user."""
    notif = Notification.objects.create(
        user_id=user_id,
        title=title,
        body=body,
        type=notif_type or '',
        data=data or {},
    )
    payload = _serialize_notification(notif)
    _push_ws(user_id, payload)
    if send_push:
        fcm_data = {**payload['data'], 'type': notif.type or ''}
        fcm_data.setdefault('order_id', str(fcm_data.get('order_id', '')))
        _push_fcm(user_id, title=title, body=body, data=fcm_data)
    return notif


def notify_users(
    user_ids: Iterable[int],
    *,
    title: str,
    body: str,
    notif_type: str = '',
    data: Optional[Dict[str, Any]] = None,
    send_push: bool = True,
) -> List[Notification]:
    seen = set()
    out: List[Notification] = []
    for uid in user_ids:
        if not uid or uid in seen:
            continue
        seen.add(uid)
        out.append(
            notify_user(
                uid,
                title=title,
                body=body,
                notif_type=notif_type,
                data=data,
                send_push=send_push,
            ),
        )
    return out
