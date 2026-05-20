"""Notification inbox helpers (REST + WS `notif_{user_id}`)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.db.models import QuerySet

from apps.core.enums import UserGroup
from apps.orders.views import user_is_courier, user_is_operator_or_super_admin, user_is_super_admin
from apps.realtime.models import Notification
from apps.realtime.serializers import NotificationSerializer

# Mijoz (oddiy user) — order_* va chat
CUSTOMER_NOTIFICATION_PREFIXES = ('order_', 'chat_')

# Operator / Super Admin
STAFF_NOTIFICATION_PREFIXES = ('staff_', 'chat_')

# Kuryer
COURIER_NOTIFICATION_PREFIXES = ('courier_',)


def detect_notification_audience(user) -> str:
    if user_is_courier(user):
        return 'courier'
    if user_is_operator_or_super_admin(user) or user_is_super_admin(user):
        return 'staff'
    return 'customer'


def _filter_by_prefixes(qs: QuerySet, prefixes: Tuple[str, ...]) -> QuerySet:
    from django.db.models import Q

    q = Q()
    for prefix in prefixes:
        q |= Q(type__startswith=prefix)
    return qs.filter(q)


def notifications_queryset(
    user,
    *,
    audience: Optional[str] = None,
    is_read: Optional[bool] = None,
    notif_type: Optional[str] = None,
) -> QuerySet:
    qs = Notification.objects.filter(user=user).order_by('-created_at', '-id')
    audience = audience or detect_notification_audience(user)

    if audience == 'staff':
        qs = _filter_by_prefixes(qs, STAFF_NOTIFICATION_PREFIXES)
    elif audience == 'courier':
        qs = _filter_by_prefixes(qs, COURIER_NOTIFICATION_PREFIXES)
    elif audience == 'customer':
        qs = _filter_by_prefixes(qs, CUSTOMER_NOTIFICATION_PREFIXES)

    if is_read is not None:
        qs = qs.filter(is_read=is_read)
    if notif_type:
        qs = qs.filter(type=notif_type)
    return qs


def build_notifications_response(
    request,
    *,
    audience: Optional[str] = None,
    is_read: Optional[bool] = None,
) -> Dict[str, Any]:
    user = request.user
    audience = audience or detect_notification_audience(user)

    if is_read is None:
        is_read_param = request.query_params.get('is_read')
        if is_read_param is not None:
            is_read = str(is_read_param).lower() in ('true', '1', 'yes')

    notif_type = (request.query_params.get('type') or '').strip() or None

    try:
        limit = min(int(request.query_params.get('limit', 50)), 100)
    except (TypeError, ValueError):
        limit = 50
    try:
        offset = max(int(request.query_params.get('offset', 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    base_qs = notifications_queryset(
        user,
        audience=audience,
        is_read=is_read,
        notif_type=notif_type,
    )
    total = base_qs.count()
    unread_count = base_qs.filter(is_read=False).count()
    page = base_qs[offset : offset + limit]

    return {
        'audience': audience,
        'role': _role_label(user),
        'unread_count': unread_count,
        'count': total,
        'limit': limit,
        'offset': offset,
        'results': NotificationSerializer(page, many=True).data,
    }


def _role_label(user) -> str:
    if user_is_super_admin(user):
        return UserGroup.SUPER_ADMIN.value
    if user.groups.filter(name=UserGroup.OPERATOR.value).exists():
        return UserGroup.OPERATOR.value
    if user_is_courier(user):
        return UserGroup.COURIER.value
    return UserGroup.USER.value
