"""OTP generation: real random code or fixed test code (Eskiz off)."""
from __future__ import annotations

import random
import string

from django.conf import settings


def generate_otp(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))


def otp_test_code() -> str:
    """Fixed OTP when OTP_TEST_CODE is set in env (e.g. 1111). Empty = production mode."""
    return (getattr(settings, 'OTP_TEST_CODE', '') or '').strip()


def is_otp_test_mode() -> bool:
    return bool(otp_test_code())


def resolve_login_otp(*, store_review_code: str | None = None) -> str:
    """
    Priority:
    1) App Store review phone OTP (caller passes it)
    2) OTP_TEST_CODE (all phones, e.g. 1111 while Eskiz is down)
    3) Random 6-digit
    """
    if store_review_code:
        return store_review_code
    test = otp_test_code()
    if test:
        return test
    return generate_otp()
