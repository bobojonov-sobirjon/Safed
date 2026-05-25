"""Foydalanuvchini o‘chirish / deaktivatsiya (PROTECT bog‘lanishlar uchun)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import CustomUser, UserDevice


class UserDeleteError(Exception):
    def __init__(self, message: str, *, code: str = 'error'):
        self.message = message
        self.code = code
        super().__init__(message)


def user_delete_blockers(user: CustomUser) -> List[str]:
    """Nima uchun hard delete mumkin emas — qisqa ro‘yxat."""
    blockers: List[str] = []
    from apps.orders.models import Order, OrderCourier

    order_count = Order.objects.filter(user_id=user.pk).count()
    if order_count:
        blockers.append(f'orders_as_customer:{order_count}')

    courier_count = OrderCourier.objects.filter(courier_id=user.pk).count()
    if courier_count:
        blockers.append(f'orders_as_courier:{courier_count}')

    try:
        from apps.inventory.models import StockReceipt

        receipt_count = StockReceipt.objects.filter(created_by_id=user.pk).count()
        if receipt_count:
            blockers.append(f'inventory_receipts:{receipt_count}')
    except Exception:
        pass

    return blockers


@transaction.atomic
def deactivate_user(user: CustomUser) -> CustomUser:
    """Soft delete: is_active=false, guruhlar va FCM o‘chiriladi, telefon bo‘shatiladi."""
    UserDevice.objects.filter(user=user).update(is_active=False)
    user.groups.clear()
    user.is_active = False
    user.is_verified = False
    if user.phone and not str(user.phone).startswith('deleted_'):
        user.phone = f'deleted_{user.pk}'
    user.save(
        update_fields=['phone', 'is_active', 'is_verified', 'updated_at'],
    )
    return user


def delete_or_deactivate_user(user: CustomUser) -> Dict[str, Any]:
    """
    Bog‘liq buyurtmalar bo‘lsa — deaktivatsiya.
    Bog‘lanish yo‘q bo‘lsa — DB dan o‘chirish.
    """
    blockers = user_delete_blockers(user)
    if blockers:
        deactivate_user(user)
        return {
            'deleted': False,
            'deactivated': True,
            'detail': (
                'Пользователь деактивирован. Полное удаление невозможно: '
                'есть заказы или другие связанные данные.'
            ),
            'blockers': blockers,
        }

    try:
        user.delete()
        return {'deleted': True, 'deactivated': False, 'detail': 'Пользователь удалён.'}
    except ProtectedError:
        deactivate_user(user)
        return {
            'deleted': False,
            'deactivated': True,
            'detail': (
                'Пользователь деактивирован. Полное удаление невозможно: '
                'есть связанные записи в системе.'
            ),
            'blockers': user_delete_blockers(user),
        }
