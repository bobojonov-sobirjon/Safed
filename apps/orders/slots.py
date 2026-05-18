"""
Checkout delivery slots: hourly grid (today / tomorrow).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from django.utils import timezone
from django.utils.dateparse import parse_date

from .busy_slot_schedule import build_day_payload


def _local_now() -> datetime:
    return timezone.localtime(timezone.now())


def today_tomorrow_dates() -> Tuple[date, date]:
    d0 = _local_now().date()
    return d0, d0 + timedelta(days=1)


def day_payload_for_date(d: date, *, tab: Optional[str] = None) -> Dict[str, Any]:
    now = _local_now()
    payload = build_day_payload(
        d,
        apply_delivery_cutoff=(d == now.date()),
        now=now,
    )
    if tab is not None:
        payload['tab'] = tab
    return payload


def availability_payload(
    relative: Optional[str] = None,
    *,
    on_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    relative: 'today' | 'tomorrow', or pass on_date (YYYY-MM-DD).
    Slots are generated automatically; closed only when used >= limit or cutoff (today).
    """
    today, tomorrow = today_tomorrow_dates()
    if on_date is not None:
        d = on_date
        tab = None
    elif (relative or 'today').lower() == 'tomorrow':
        d = tomorrow
        tab = 'tomorrow'
    else:
        d = today
        tab = 'today'
    return day_payload_for_date(d, tab=tab)


def parse_date_query(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return parse_date(value.strip())
