"""
App Store / Google Play review demo account (fixed phone + OTP from .env).
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from django.conf import settings


def _digits_only(phone: str) -> str:
    return re.sub(r'\D', '', phone or '')


def store_review_credentials() -> Optional[Tuple[str, str]]:
    """Return (normalized_phone, otp_code) if configured, else None."""
    phone = _digits_only(getattr(settings, 'STORE_REVIEW_USER_PHONE', '') or '')
    otp = (getattr(settings, 'STORE_REVIEW_USER_OTP', '') or '').strip()
    if not phone or not otp:
        return None
    return phone, otp


def is_store_review_phone(phone: str) -> bool:
    creds = store_review_credentials()
    if not creds:
        return False
    return _digits_only(phone) == creds[0]


def is_store_review_login(phone: str, code: str) -> bool:
    creds = store_review_credentials()
    if not creds:
        return False
    review_phone, review_otp = creds
    return _digits_only(phone) == review_phone and (code or '').strip() == review_otp


def store_review_otp_code() -> Optional[str]:
    creds = store_review_credentials()
    return creds[1] if creds else None
