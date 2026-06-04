"""Chat WS xabari: DB + FCM push; notification WS — ChatConsumer (async)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from django.contrib.auth import get_user_model

from apps.accounts.views import (
    GROUP_COURIER,
    GROUP_OPERATOR,
    user_in_group,
    user_is_staff,
)
from apps.realtime.models import Notification
from apps.realtime.services.notify import _serialize_notification, notify_user

logger = logging.getLogger(__name__)
User = get_user_model()

_MESSAGE_PREVIEW_MAX = 120


def _sender_display_name(sender) -> str:
    name = f'{sender.first_name or ""} {sender.last_name or ""}'.strip()
    if name:
        return name
    phone = (sender.phone or '').strip()
    if phone:
        return phone
    return 'Пользователь'


def _truncate_message(text: str, limit: int = _MESSAGE_PREVIEW_MAX) -> str:
    value = (text or '').strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + '…'


def _sender_role_key(sender) -> str:
    if user_in_group(sender, GROUP_COURIER):
        return 'courier'
    if user_in_group(sender, GROUP_OPERATOR):
        return 'operator'
    if user_is_staff(sender):
        return 'staff'
    return 'customer'


def build_chat_push_texts(
    *,
    sender,
    receiver,
    order_id: Optional[int],
    message_preview: str,
) -> Tuple[str, str]:
    """
    Push title/body (rus): kimdan → kimga + buyurtma + xabar qisqacha.
    initiator = mijoz, receiver = operator (loyiha konventsiyasi).
    """
    sender_name = _sender_display_name(sender)
    preview = _truncate_message(message_preview)
    order_ref = f'№{order_id}' if order_id else ''
    sender_role = _sender_role_key(sender)
    receiver_is_staff = user_is_staff(receiver)
    sender_is_staff = user_is_staff(sender)

    # Mijoz → operator / xodim
    if sender_role == 'customer' and receiver_is_staff:
        title = 'Сообщение от покупателя'
        if preview:
            body = (
                f'Заказ {order_ref} · {sender_name}: {preview}'
                if order_ref
                else f'{sender_name}: {preview}'
            )
        else:
            body = f'Заказ {order_ref} — новое сообщение в чате' if order_ref else f'{sender_name} написал в чате'
        return title, body

    # Operator → mijoz
    if sender_role == 'operator' and not receiver_is_staff:
        title = 'Сообщение от оператора'
        if preview:
            body = (
                f'По заказу {order_ref}: {preview}'
                if order_ref
                else preview
            )
        else:
            body = f'Оператор ответил по заказу {order_ref}' if order_ref else 'Оператор написал вам в чате'
        if sender_name and sender_name != 'Пользователь':
            body = f'{sender_name} · {body}' if preview else f'Оператор {sender_name} · {body}'
        return title, body

    # Kuryer → mijoz
    if sender_role == 'courier' and not receiver_is_staff:
        title = 'Сообщение от курьера'
        body = (
            f'Заказ {order_ref} · {sender_name}: {preview}'
            if preview and order_ref
            else (f'{sender_name}: {preview}' if preview else f'Курьер написал по заказу {order_ref}')
        )
        return title, body

    # Kuryer → operator
    if sender_role == 'courier' and receiver_is_staff:
        title = 'Сообщение от курьера'
        body = (
            f'Заказ {order_ref} · {sender_name}: {preview}'
            if preview
            else f'Курьер · заказ {order_ref}'
        )
        return title, body

    # Boshqa xodim (Admin / Super Admin) → mijoz
    if sender_is_staff and not receiver_is_staff:
        title = 'Сообщение от поддержки'
        body = (
            f'По заказу {order_ref}: {preview}'
            if preview and order_ref
            else (preview or f'Новое сообщение по заказу {order_ref}')
        )
        return title, body

    # Mijoz → boshqa (fallback)
    if not sender_is_staff and receiver_is_staff:
        title = f'Чат · {sender_name}'
        body = preview or 'Новое сообщение в чате заказа'
        if order_ref:
            body = f'Заказ {order_ref}: {body}'
        return title, body

    # Umumiy fallback
    title = f'Новое сообщение · {sender_name}'
    body = preview or 'Откройте чат в приложении'
    if order_ref:
        body = f'Заказ {order_ref} — {body}'
    return title, body


def notify_chat_receiver(
    *,
    receiver_id: int,
    room_id: int,
    order_id: Optional[int],
    sender_id: int,
    message_id: int,
    message_preview: str,
    sender=None,
    receiver=None,
) -> Notification:
    """
    Qabul qiluvchiga chat: Notification DB + FCM.
    WS `notif_{receiver_id}` — ChatConsumer async yuboradi.
    """
    if sender is None:
        sender = User.objects.only('id', 'phone', 'first_name', 'last_name').get(pk=sender_id)
    if receiver is None:
        receiver = User.objects.only('id', 'phone', 'first_name', 'last_name').get(pk=receiver_id)

    title, body = build_chat_push_texts(
        sender=sender,
        receiver=receiver,
        order_id=order_id,
        message_preview=message_preview,
    )

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
            'sender_name': _sender_display_name(sender),
            'sender_role': _sender_role_key(sender),
        },
        send_push=True,
        send_ws=False,
    )
    logger.info(
        'Chat push room=%s order=%s from=%s(%s) to=%s title=%r',
        room_id,
        order_id,
        sender_id,
        _sender_role_key(sender),
        receiver_id,
        title,
    )
    return notif


def chat_notification_ws_payload(notif: Notification) -> Dict[str, Any]:
    """NotificationConsumer uchun WS JSON."""
    return _serialize_notification(notif)
