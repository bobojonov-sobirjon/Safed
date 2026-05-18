"""
Hourly delivery grid: working hours + order count per hour vs capacity limit.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone as dj_timezone

from apps.core.enums import OrderStatus

DELIVERY_WINDOW_FULL_MESSAGE = (
    'На выбранную дату и время слишком много заказов. '
    'Выберите другой день или время.'
)
DELIVERY_WINDOW_CUTOFF_MESSAGE = (
    'Слишком поздно для выбранного времени доставки. Выберите более поздний слот или другой день.'
)


def get_hourly_delivery_capacity() -> int:
    from .pricing import get_fee_settings

    cap = int(get_fee_settings().hourly_delivery_capacity or 15)
    return max(1, cap)


def _default_working_bounds() -> Tuple[time, time]:
    return time(6, 0), time(23, 0)


def get_working_time_bounds_default() -> Tuple[time, time]:
    """Fallback from settings when there is no BusyDayWorkingHours row for that date."""
    start_s = getattr(settings, 'BUSY_SLOT_WORKING_START', '06:00')
    end_s = getattr(settings, 'BUSY_SLOT_WORKING_END', '23:00')
    if not isinstance(start_s, str):
        start_s = str(start_s)
    if not isinstance(end_s, str):
        end_s = str(end_s)
    try:
        return parse_time_flexible(start_s), parse_time_flexible(end_s)
    except ValueError:
        return _default_working_bounds()


def get_working_time_bounds_for_date(d: date) -> Tuple[time, time]:
    """Per-day window from admin (BusyDayWorkingHours), else settings default."""
    from .models import BusyDayWorkingHours

    row = BusyDayWorkingHours.objects.filter(date=d).only('working_start', 'working_end').first()
    if row:
        return row.working_start, row.working_end
    return get_working_time_bounds_default()


def parse_time_flexible(value: str) -> time:
    v = (value or '').strip()
    if not v:
        raise ValueError('empty')
    if ':' in v:
        parts = v.split(':')
    elif '-' in v:
        parts = v.split('-')
    else:
        raise ValueError('invalid')
    if len(parts) != 2:
        raise ValueError('invalid')
    h, m = int(parts[0]), int(parts[1])
    return time(h, m)


def time_to_hhmm(t: time) -> str:
    return f'{t.hour:02d}:{t.minute:02d}'


def _combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def intervals_overlap(
    a_start: time,
    a_end: time,
    b_start: time,
    b_end: time,
    day: date,
) -> bool:
    """Half-open [start, end) on the same calendar day."""
    a0 = _combine(day, a_start)
    a1 = _combine(day, a_end)
    b0 = _combine(day, b_start)
    b1 = _combine(day, b_end)
    return a0 < b1 and b0 < a1


def iter_hour_slots(day_start: time, day_end: time) -> List[Tuple[time, time]]:
    """
    Hourly slots [t, t+1h) from day_start inclusive until last slot ends at day_end.
    Example: 06:00–23:00 → slots ending 07:00 … 23:00 (last 22:00–23:00).
    """
    slots: List[Tuple[time, time]] = []
    cur = datetime.combine(date.min, day_start)
    end_dt = datetime.combine(date.min, day_end)
    while cur + timedelta(hours=1) <= end_dt:
        t0 = cur.time()
        t1 = (cur + timedelta(hours=1)).time()
        slots.append((t0, t1))
        cur += timedelta(hours=1)
    return slots


def working_hours_label(day_start: time, day_end: time) -> str:
    return f'{time_to_hhmm(day_start)}-{time_to_hhmm(day_end)}'


def hour_slot_cutoff_passed(d: date, hour_start: time, now: Optional[datetime] = None) -> bool:
    """True if local now is within 30 minutes before slot start (same calendar day)."""
    now = now or dj_timezone.localtime(dj_timezone.now())
    if d != now.date():
        return False
    start_naive = datetime.combine(d, hour_start)
    tz = dj_timezone.get_current_timezone()
    if dj_timezone.is_naive(start_naive):
        start_dt = dj_timezone.make_aware(start_naive, tz)
    else:
        start_dt = start_naive
    return now >= start_dt - timedelta(minutes=30)


def count_orders_in_hour(
    d: date,
    hour_start: time,
    hour_end: time,
    orders: List[Any],
) -> int:
    """Active orders whose delivery window overlaps [hour_start, hour_end)."""
    n = 0
    for o in orders:
        if intervals_overlap(hour_start, hour_end, o.delivery_time_start, o.delivery_time_end, d):
            n += 1
    return n


def build_day_payload(
    d: date,
    *,
    exclude_order_id: Optional[int] = None,
    apply_delivery_cutoff: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    from .models import Order

    w0, w1 = get_working_time_bounds_for_date(d)

    orders_qs = Order.objects.filter(
        delivery_date=d,
        delivery_time_start__isnull=False,
        delivery_time_end__isnull=False,
        status__in=OrderStatus.active_statuses(),
        is_deleted=False,
    )
    if exclude_order_id is not None:
        orders_qs = orders_qs.exclude(pk=exclude_order_id)
    orders = list(orders_qs.only('id', 'delivery_time_start', 'delivery_time_end'))
    limit = get_hourly_delivery_capacity()
    if apply_delivery_cutoff:
        now = now or dj_timezone.localtime(dj_timezone.now())

    slots_out: List[Dict[str, Any]] = []
    for s0, s1 in iter_hour_slots(w0, w1):
        used = count_orders_in_hour(d, s0, s1, orders)
        available = used < limit
        disabled_reason: Optional[str] = None
        if used >= limit:
            disabled_reason = 'full'
            available = False
        elif apply_delivery_cutoff and hour_slot_cutoff_passed(d, s0, now):
            disabled_reason = 'cutoff'
            available = False
        slots_out.append({
            'start': time_to_hhmm(s0),
            'end': time_to_hhmm(s1),
            'used': used,
            'limit': limit,
            'available': available,
            'disabled_reason': disabled_reason,
        })

    return {
        'date': d.isoformat(),
        'working_hours': working_hours_label(w0, w1),
        'hourly_order_limit': limit,
        'slots': slots_out,
    }


def validate_delivery_window(
    d: date,
    start: time,
    end: time,
    *,
    exclude_order_id: Optional[int] = None,
) -> Optional[str]:
    """Return error message or None if OK."""
    if end <= start:
        return 'Время окончания должно быть позже времени начала.'

    w0, w1 = get_working_time_bounds_for_date(d)
    if start < w0 or end > w1:
        return 'Интервал доставки вне рабочих часов.'

    now = dj_timezone.localtime(dj_timezone.now())
    apply_cutoff = d == now.date()
    payload = build_day_payload(
        d,
        exclude_order_id=exclude_order_id,
        apply_delivery_cutoff=apply_cutoff,
        now=now,
    )
    for row in payload['slots']:
        s0 = parse_time_flexible(row['start'])
        s1 = parse_time_flexible(row['end'])
        if not intervals_overlap(start, end, s0, s1, d):
            continue
        if not row.get('available'):
            reason = row.get('disabled_reason')
            if reason == 'full':
                return DELIVERY_WINDOW_FULL_MESSAGE
            if reason == 'cutoff':
                return DELIVERY_WINDOW_CUTOFF_MESSAGE
            return DELIVERY_WINDOW_FULL_MESSAGE
    return None
