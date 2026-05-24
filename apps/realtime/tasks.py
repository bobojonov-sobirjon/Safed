"""Celery tasks for realtime / push."""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _daily_cart_reminder_enabled() -> bool:
    return getattr(settings, 'DAILY_CART_REMINDER_ENABLED', True)


@shared_task(name='apps.realtime.tasks.send_daily_cart_reminder_push')
def send_daily_cart_reminder_push() -> dict:
    """Har kuni soat 10:00 (Asia/Tashkent) — barcha FCM qurilmalarga savat eslatmasi."""
    if not _daily_cart_reminder_enabled():
        logger.info('Daily cart reminder push disabled (DAILY_CART_REMINDER_ENABLED)')
        return {'skipped': True, 'reason': 'disabled'}

    from apps.realtime.services.marketing_push import send_daily_cart_reminder_to_all

    return send_daily_cart_reminder_to_all()
