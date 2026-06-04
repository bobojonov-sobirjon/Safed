"""CLICK Merchant API client (outgoing requests)."""
from __future__ import annotations

import hashlib
import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CLICK_MERCHANT_TIMEOUT = 30


class ClickMerchantError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = 'click_error',
        error_code: Optional[int] = None,
    ):
        self.message = message
        self.code = code
        self.error_code = error_code
        super().__init__(message)


def _merchant_config() -> Dict[str, Any]:
    return {
        'base_url': str(
            getattr(settings, 'CLICK_MERCHANT_API_URL', 'https://api.click.uz/v2/merchant')
        ).rstrip('/'),
        'service_id': int(getattr(settings, 'CLICK_SERVICE_ID', 0) or 0),
        'merchant_user_id': int(getattr(settings, 'CLICK_MERCHANT_USER_ID', 0) or 0),
        'secret_key': str(getattr(settings, 'CLICK_SECRET_KEY', '') or ''),
    }


def merchant_api_configured() -> bool:
    cfg = _merchant_config()
    return bool(cfg['service_id'] and cfg['merchant_user_id'] and cfg['secret_key'])


def click_refund_auto_enabled() -> bool:
    return bool(getattr(settings, 'CLICK_REFUND_AUTO', True))


def build_auth_header() -> str:
    cfg = _merchant_config()
    timestamp = str(int(time.time()))
    digest = hashlib.sha1(f"{timestamp}{cfg['secret_key']}".encode('utf-8')).hexdigest()
    return f"{cfg['merchant_user_id']}:{digest}:{timestamp}"


def amount_path_segment(amount: Decimal) -> str:
    return f'{amount.quantize(Decimal("0.01")):.2f}'


def _parse_response_payload(response: requests.Response) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise ClickMerchantError(
            f'CLICK javob JSON emas (HTTP {response.status_code}).',
            code='invalid_response',
        ) from exc
    if not isinstance(data, dict):
        raise ClickMerchantError('CLICK javob formati noto‘g‘ri.', code='invalid_response')
    return data


def _merchant_error_code(data: Dict[str, Any]) -> int:
    raw = data.get('error_code', data.get('error', 0))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def _merchant_error_note(data: Dict[str, Any]) -> str:
    return str(data.get('error_note') or data.get('error_note'.upper()) or '').strip()


def _request(method: str, path: str) -> Dict[str, Any]:
    if not merchant_api_configured():
        raise ClickMerchantError('CLICK Merchant API sozlanmagan.', code='not_configured')

    cfg = _merchant_config()
    url = f"{cfg['base_url']}/{path.lstrip('/')}"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Auth': build_auth_header(),
    }

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=CLICK_MERCHANT_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.exception('CLICK Merchant API request failed method=%s path=%s', method, path)
        raise ClickMerchantError('CLICK API bilan bog‘lanib bo‘lmadi.', code='network') from exc

    data = _parse_response_payload(response)
    error_code = _merchant_error_code(data)
    if response.status_code >= 400 or error_code != 0:
        note = _merchant_error_note(data) or f'HTTP {response.status_code}'
        raise ClickMerchantError(note, code='click_rejected', error_code=error_code)
    return data


def resolve_click_payment_id(*, click_paydoc_id: Optional[int], click_trans_id: Optional[int]) -> int:
    payment_id = click_paydoc_id or click_trans_id
    if not payment_id:
        raise ClickMerchantError('CLICK payment_id topilmadi.', code='payment_id')
    return int(payment_id)


def partial_reversal(payment_id: int, amount: Decimal) -> Dict[str, Any]:
    """DELETE /payment/partial_reversal/{service_id}/{payment_id}/{amount}"""
    cfg = _merchant_config()
    amt = amount_path_segment(amount)
    path = f"payment/partial_reversal/{cfg['service_id']}/{int(payment_id)}/{amt}"
    logger.info('CLICK partial_reversal payment_id=%s amount=%s', payment_id, amt)
    return _request('DELETE', path)


def full_reversal(payment_id: int) -> Dict[str, Any]:
    """DELETE /payment/reversal/{service_id}/{payment_id}"""
    cfg = _merchant_config()
    path = f"payment/reversal/{cfg['service_id']}/{int(payment_id)}"
    logger.info('CLICK full_reversal payment_id=%s', payment_id)
    return _request('DELETE', path)


def payment_status(payment_id: int) -> Dict[str, Any]:
    cfg = _merchant_config()
    path = f"payment/status/{cfg['service_id']}/{int(payment_id)}"
    return _request('GET', path)
