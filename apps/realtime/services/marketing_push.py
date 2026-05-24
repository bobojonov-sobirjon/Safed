"""Marketing / retention FCM pushes (no DB notification row)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from django.contrib.auth import get_user_model

from apps.accounts.models import UserDevice
from apps.realtime.services.fcm import send_fcm_to_tokens

logger = logging.getLogger(__name__)
User = get_user_model()

# Kunlik savat eslatmasi — faqat o‘zbekcha (Uzum Market uslubida)
DAILY_CART_REMINDER_TITLE = "Siz ularni unutdingiz!"
DAILY_CART_REMINDER_BODY = "Savatdagi mahsulotlar sizni kutyapti 💜"

FCM_BATCH_SIZE = 500


def _active_device_tokens() -> List[str]:
    return list(
        UserDevice.objects.filter(
            is_active=True,
            user__is_active=True,
        )
        .exclude(device_token='')
        .values_list('device_token', flat=True)
        .distinct(),
    )


def send_daily_cart_reminder_to_all() -> Dict[str, Any]:
    """
    FCM push barcha faol qurilmalarga (har kuni 10:00 da Celery Beat orqali).
    Savat serverda saqlanmaydi — umumiy eslatma.
    """
    tokens = _active_device_tokens()
    if not tokens:
        logger.info('Daily cart reminder: no active device tokens')
        return {'tokens': 0, 'sent': 0, 'users_with_devices': 0}

    users_count = (
        User.objects.filter(is_active=True, devices__is_active=True)
        .distinct()
        .count()
    )
    data = {
        'type': 'daily_cart_reminder',
        'event': 'daily_cart_reminder',
        'screen': 'cart',
    }
    sent = 0
    for i in range(0, len(tokens), FCM_BATCH_SIZE):
        chunk = tokens[i : i + FCM_BATCH_SIZE]
        sent += send_fcm_to_tokens(
            chunk,
            title=DAILY_CART_REMINDER_TITLE,
            body=DAILY_CART_REMINDER_BODY,
            data=data,
        )

    logger.info(
        'Daily cart reminder: tokens=%s sent=%s users=%s',
        len(tokens),
        sent,
        users_count,
    )
    return {
        'tokens': len(tokens),
        'sent': sent,
        'users_with_devices': users_count,
    }
