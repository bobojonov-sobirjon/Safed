"""
Order-related push + WebSocket notifications (Russian copy).
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.core.enums import OrderStatus, PaymentType, UserGroup
from apps.realtime.services.notify import notify_user, notify_users

logger = logging.getLogger(__name__)
User = get_user_model()

# --- Russian texts per event (not generic "status changed") ---

STATUS_CUSTOMER_BODY: Dict[str, str] = {
    OrderStatus.CONFIRMED.value: (
        'Ваш заказ подтверждён и передан в сборку. Мы уже готовим вашу корзину.'
    ),
    OrderStatus.PICKING.value: (
        'Заказ собирается на складе — проверяем каждую позицию перед отправкой.'
    ),
    OrderStatus.SHIPPED.value: (
        'Заказ передан курьеру и уже в пути к вам.'
    ),
    OrderStatus.DELIVERED.value: (
        'Курьер у вашего адреса. Пожалуйста, будьте на связи.'
    ),
    OrderStatus.COMPLETED.value: (
        'Заказ выполнен. Оплата подтверждена. Спасибо за покупку!'
    ),
    OrderStatus.REJECTED.value: (
        'К сожалению, мы не можем выполнить этот заказ. Свяжитесь с поддержкой, если нужна помощь.'
    ),
    OrderStatus.CANCELLED.value: (
        'Заказ отменён. Если оплата была списана, возврат оформится по правилам сервиса.'
    ),
}

STAFF_NEW_ORDER_TITLE = 'Новый заказ'
STAFF_NEW_ORDER_BODY_CASH = 'Заказ №{order_id} на сумму {amount} сум — оплата наличными при получении.'
STAFF_NEW_ORDER_BODY_CARD = 'Заказ №{order_id} на сумму {amount} сум — оплата картой подтверждена.'

CUSTOMER_CLICK_PAID_TITLE = 'Оплата получена'
CUSTOMER_CLICK_PAID_BODY = (
    'Оплата через Click успешно проведена. Заказ №{order_id} принят в обработку.'
)

CUSTOMER_CASH_CONFIRM_TITLE = 'Доставка завершена'
CUSTOMER_CASH_CONFIRM_BODY = (
    'Курьер подтвердил оплату. Вы получили заказ? Подтвердите получение в приложении.'
)

CUSTOMER_COURIER_ASSIGNED_TITLE = 'Курьер в пути'
CUSTOMER_COURIER_ASSIGNED_BODY = (
    'Курьер назначен — заказ №{order_id} скоро будет доставлен. Следите за статусом в приложении.'
)

CUSTOMER_DELIVERED_TITLE = 'Курьер на месте'
CUSTOMER_DELIVERED_BODY = (
    'Курьер прибыл по вашему адресу. Заказ №{order_id} готов к получению. Пожалуйста, будьте на связи.'
)

COURIER_NEW_ORDER_TITLE = 'Новый заказ'
COURIER_NEW_ORDER_BODY = 'Вам назначен заказ №{order_id}. Адрес и детали — в разделе «Мои доставки».'

CUSTOMER_HANDLING_TITLE = 'Заказ в работе'
CUSTOMER_HANDLING_BODY = (
    'Оператор взял ваш заказ №{order_id} в работу. Скоро начнётся сборка.'
)

PICKING_SCAN_TITLE = 'Сборка заказа'
PICKING_SCAN_BODY = (
    'По заказу №{order_id} отсканирован товар. Сумма может обновиться после проверки веса.'
)

PICKING_LINE_TITLE = 'Сборка заказа'
PICKING_LINE_BODY = (
    'По заказу №{order_id} уточнено количество товара. Проверьте итоговую сумму в приложении.'
)

STAFF_ORDER_CANCELLED_TITLE = 'Отмена заказа'
STAFF_ORDER_CANCELLED_BODY = (
    'Заказ №{order_id} отменён покупателем. Проверьте детали в списке заказов.'
)

STAFF_CUSTOMER_DELIVERY_RESPONSE_TITLE = 'Ответ покупателя'
STAFF_CUSTOMER_ACCEPT_DELIVERY_BODY = (
    'Заказ №{order_id}: покупатель подтвердил, что получил заказ.'
)
STAFF_CUSTOMER_REJECT_DELIVERY_BODY = (
    'Заказ №{order_id}: покупатель сообщил о проблеме с получением. Требуется проверка.'
)


def _order_amount_str(order) -> str:
    total = order.estimated_total or order.total_amount or Decimal('0')
    return f'{total.quantize(Decimal("0.01")):.2f}'


def _staff_user_ids() -> list[int]:
    return list(
        User.objects.filter(
            is_active=True,
            groups__name__in=[
                UserGroup.OPERATOR.value,
                UserGroup.SUPER_ADMIN.value,
            ],
        )
        .distinct()
        .values_list('id', flat=True),
    )


def _order_payload(order_id: int, **extra) -> Dict[str, Any]:
    return {'order_id': order_id, **extra}


def notify_staff_customer_delivery_response(order_id: int, *, accepted: bool) -> None:
    """Operator / Super Admin — faqat WS (in-app notification)."""
    body = (
        STAFF_CUSTOMER_ACCEPT_DELIVERY_BODY
        if accepted
        else STAFF_CUSTOMER_REJECT_DELIVERY_BODY
    ).format(order_id=order_id)
    notify_users(
        _staff_user_ids(),
        title=STAFF_CUSTOMER_DELIVERY_RESPONSE_TITLE,
        body=body,
        notif_type='staff_customer_delivery_response',
        data=_order_payload(
            order_id,
            event='staff_customer_delivery_response',
            accepted=accepted,
        ),
        send_push=False,
    )
    logger.info('Staff WS customer delivery response order=%s accepted=%s', order_id, accepted)


def notify_staff_order_cancelled(order_id: int) -> None:
    notify_users(
        _staff_user_ids(),
        title=STAFF_ORDER_CANCELLED_TITLE,
        body=STAFF_ORDER_CANCELLED_BODY.format(order_id=order_id),
        notif_type='staff_order_cancelled',
        data=_order_payload(order_id, event='staff_order_cancelled'),
    )
    logger.info('Staff notified order cancelled=%s', order_id)


def notify_staff_new_order(order_id: int) -> None:
    from apps.orders.models import Order

    try:
        order = Order.objects.only(
            'id', 'estimated_total', 'total_amount', 'payment_type',
        ).get(pk=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return

    if order.payment_type == PaymentType.CASH.value:
        body = STAFF_NEW_ORDER_BODY_CASH.format(
            order_id=order.pk,
            amount=_order_amount_str(order),
        )
    else:
        body = STAFF_NEW_ORDER_BODY_CARD.format(
            order_id=order.pk,
            amount=_order_amount_str(order),
        )

    data = _order_payload(order.pk, event='staff_new_order', payment_type=order.payment_type)
    notify_users(
        _staff_user_ids(),
        title=STAFF_NEW_ORDER_TITLE,
        body=body,
        notif_type='staff_new_order',
        data=data,
    )
    logger.info('Staff notified new order=%s', order.pk)


def notify_customer_click_paid(order_id: int) -> None:
    notify_user(
        _order_user_id(order_id),
        title=CUSTOMER_CLICK_PAID_TITLE,
        body=CUSTOMER_CLICK_PAID_BODY.format(order_id=order_id),
        notif_type='order_click_paid',
        data=_order_payload(order_id, event='order_click_paid'),
    )


def notify_customer_cash_confirmed(order_id: int) -> None:
    notify_user(
        _order_user_id(order_id),
        title=CUSTOMER_CASH_CONFIRM_TITLE,
        body=CUSTOMER_CASH_CONFIRM_BODY,
        notif_type='order_cash_confirmed',
        data=_order_payload(order_id, event='order_cash_confirmed'),
    )


def notify_customer_delivered(order_id: int) -> None:
    """Mijozga: kuryer manzilga yetdi (push + WS)."""
    notify_user(
        _order_user_id(order_id),
        title=CUSTOMER_DELIVERED_TITLE,
        body=CUSTOMER_DELIVERED_BODY.format(order_id=order_id),
        notif_type='order_delivered',
        data=_order_payload(
            order_id,
            event='order_delivered',
            status=OrderStatus.DELIVERED.value,
        ),
    )
    logger.info('Customer delivered push order=%s', order_id)


def notify_customer_status_change(order_id: int, new_status: str) -> None:
    if new_status == OrderStatus.DELIVERED.value:
        notify_customer_delivered(order_id)
        return
    body = STATUS_CUSTOMER_BODY.get(new_status)
    if not body:
        return
    notify_user(
        _order_user_id(order_id),
        title='Статус заказа',
        body=body,
        notif_type='order_status',
        data=_order_payload(order_id, event='order_status', status=new_status),
    )


def notify_courier_assigned(order_id: int, courier_id: int) -> None:
    """Kuryerga push + WS; mijozga alohida xabar."""
    notify_user(
        courier_id,
        title=COURIER_NEW_ORDER_TITLE,
        body=COURIER_NEW_ORDER_BODY.format(order_id=order_id),
        notif_type='courier_assigned',
        data=_order_payload(order_id, event='courier_assigned'),
        send_push=True,
    )
    notify_user(
        _order_user_id(order_id),
        title=CUSTOMER_COURIER_ASSIGNED_TITLE,
        body=CUSTOMER_COURIER_ASSIGNED_BODY.format(order_id=order_id),
        notif_type='order_courier_assigned',
        data=_order_payload(order_id, event='order_courier_assigned'),
    )
    logger.info('Courier push assigned order=%s courier=%s', order_id, courier_id)


def notify_customer_order_handling(order_id: int, staff_user_id: int) -> None:
    from apps.realtime.models import Notification

    if Notification.objects.filter(
        user_id=_order_user_id(order_id),
        type='order_handling',
        data__contains={'order_id': order_id},
    ).exists():
        return

    notify_user(
        _order_user_id(order_id),
        title=CUSTOMER_HANDLING_TITLE,
        body=CUSTOMER_HANDLING_BODY.format(order_id=order_id),
        notif_type='order_handling',
        data=_order_payload(order_id, event='order_handling', staff_user_id=staff_user_id),
    )


def notify_customer_picking_scan(order_id: int) -> None:
    notify_user(
        _order_user_id(order_id),
        title=PICKING_SCAN_TITLE,
        body=PICKING_SCAN_BODY.format(order_id=order_id),
        notif_type='order_picking_scan',
        data=_order_payload(order_id, event='order_picking_scan'),
    )


def notify_customer_picking_line(order_id: int) -> None:
    notify_user(
        _order_user_id(order_id),
        title=PICKING_LINE_TITLE,
        body=PICKING_LINE_BODY.format(order_id=order_id),
        notif_type='order_picking_line',
        data=_order_payload(order_id, event='order_picking_line'),
    )


def _order_user_id(order_id: int) -> int:
    from apps.orders.models import Order

    return Order.objects.values_list('user_id', flat=True).get(pk=order_id)


def schedule_after_commit(callback) -> None:
    transaction.on_commit(callback)


def on_order_created_cash(order_id: int) -> None:
    schedule_after_commit(lambda: notify_staff_new_order(order_id))


def on_order_click_paid(order_id: int) -> None:
    def _run():
        notify_staff_new_order(order_id)
        notify_customer_click_paid(order_id)

    schedule_after_commit(_run)


def on_status_changed(order_id: int, new_status: str, old_status: str) -> None:
    if new_status == old_status:
        return

    def _run():
        notify_customer_status_change(order_id, new_status)

    schedule_after_commit(_run)


def on_order_cancelled(order_id: int) -> None:
    def _run():
        notify_staff_order_cancelled(order_id)
        notify_customer_status_change(order_id, OrderStatus.CANCELLED.value)

    schedule_after_commit(_run)


def on_courier_assigned(order_id: int, courier_id: int) -> None:
    schedule_after_commit(lambda: notify_courier_assigned(order_id, courier_id))


def on_customer_delivery_response(order_id: int, *, accepted: bool) -> None:
    schedule_after_commit(
        lambda: notify_staff_customer_delivery_response(order_id, accepted=accepted),
    )


def on_staff_viewed_order(order_id: int, staff_user_id: int) -> None:
    schedule_after_commit(
        lambda: notify_customer_order_handling(order_id, staff_user_id),
    )


def on_picking_scan(order_id: int) -> None:
    schedule_after_commit(lambda: notify_customer_picking_scan(order_id))


def on_picking_line(order_id: int) -> None:
    schedule_after_commit(lambda: notify_customer_picking_line(order_id))


def on_cash_confirmed(order_id: int) -> None:
    schedule_after_commit(lambda: notify_customer_cash_confirmed(order_id))
