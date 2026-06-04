"""Chat WS xabari: DB + FCM push; notification WS — ChatConsumer (async)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model

from apps.realtime.models import Notification
from apps.realtime.services.notify import _serialize_notification, notify_user

logger = logging.getLogger(__name__)
User = get_user_model()


def _sender_display_name(sender) -> str:
    name = f'{sender.first_name or ""} {sender.last_name or ""}'.strip()
    return name or (sender.phone or '') or 'Новое сообщение'


def notify_chat_receiver(
    *,
    receiver_id: int,
    room_id: int,
    order_id: Optional[int],
    sender_id: int,
    message_id: int,
    message_preview: str,
    sender=None,
) -> Notification:
    """
    Qabul qiluvchiga chat: Notification DB + FCM.
    WS `notif_{receiver_id}` — ChatConsumer async yuboradi (sync_to_async ichida ishonchsiz).
    """
    if sender is None:
        sender = User.objects.only('id', 'phone', 'first_name', 'last_name').get(pk=sender_id)

    title = _sender_display_name(sender)
    body = (message_preview or '')[:100]

    notif = notify_user(
        receiver_id,
        title=title,
        body=body,
        notif_type='chat_message',
        data={
            'room_id': room_id,
            'order_id': order_id,
            'sender_id': sender_id,
            'message_id': message_id,
            'event': 'chat_message',
        },
        send_push=True,
        send_ws=False,
    )
    logger.info(
        'Chat FCM queued room=%s receiver=%s sender=%s message_id=%s',
        room_id,
        receiver_id,
        sender_id,
        message_id,
    )
    return notif


def chat_notification_ws_payload(notif: Notification) -> Dict[str, Any]:
    """NotificationConsumer uchun WS JSON."""
    return _serialize_notification(notif)
