"""
Cashback (nakapitilno): buyurtma yakunlanganda foiz bo'yicha yig'iladi.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F

from apps.accounts.models import CustomUser
from apps.orders.models import CashbackSettings, CashbackTransaction, Order

logger = logging.getLogger(__name__)


def get_cashback_settings() -> CashbackSettings:
    obj, _ = CashbackSettings.objects.get_or_create(pk=1)
    return obj


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def order_cashback_base_amount(order: Order) -> Decimal:
    """Buyurtma summasi — yakuniy yoki baholangan."""
    if order.final_total is not None:
        return _quantize_money(Decimal(str(order.final_total)))
    return _quantize_money(Decimal(str(order.estimated_total or 0)))


def compute_cashback_amount(order: Order, settings: CashbackSettings | None = None) -> Decimal:
    settings = settings or get_cashback_settings()
    if not settings.is_active:
        return Decimal('0.00')
    percent = Decimal(str(settings.cashback_percent or 0))
    if percent <= 0:
        return Decimal('0.00')
    base = order_cashback_base_amount(order)
    if base <= 0:
        return Decimal('0.00')
    return _quantize_money(base * percent / Decimal('100'))


@transaction.atomic
def accrue_order_cashback(order: Order) -> Decimal:
    """
    Idempotent: agar allaqachon hisoblangan bo'lsa, qayta bermaydi.
    Returns accrued amount.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)
    if Decimal(str(order.cashback_earned or 0)) > 0:
        return Decimal(str(order.cashback_earned))

    amount = compute_cashback_amount(order)
    if amount <= 0:
        return Decimal('0.00')

    user = CustomUser.objects.select_for_update().get(pk=order.user_id)
    CustomUser.objects.filter(pk=user.pk).update(
        cashback_balance=F('cashback_balance') + amount,
    )
    user.refresh_from_db(fields=['cashback_balance'])

    order.cashback_earned = amount
    order.save(update_fields=['cashback_earned', 'updated_at'])

    CashbackTransaction.objects.create(
        user_id=order.user_id,
        order=order,
        amount=amount,
        transaction_type=CashbackTransaction.Type.EARNED,
        balance_after=user.cashback_balance,
        note=f'Order #{order.pk}',
    )
    logger.info('Cashback accrued order=%s user=%s amount=%s', order.pk, order.user_id, amount)
    return amount
