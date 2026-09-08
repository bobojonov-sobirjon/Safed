"""
Eskiz.uz SMS gateway.

API login: email + API secret (kabinet web-paroli emas).
Tasdiqlangan shablon (nick 4546):
  Safet Go mobil ilovasiga kirish uchun tasdiqlash kodi: {code}. Kodni hech kimga bermang
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_OTP_TEMPLATE = (
    'Safet Go mobil ilovasiga kirish uchun tasdiqlash kodi: {code}. Kodni hech kimga bermang'
)
ESKIZ_LOGIN_URL = 'https://notify.eskiz.uz/api/auth/login'
ESKIZ_SEND_URL = 'https://notify.eskiz.uz/api/message/sms/send'
ESKIZ_TOKEN_CACHE_KEY = 'eskiz_sms_bearer_token'
# Eskiz token odatda uzoq yashaydi; 1 soat cache + 401 da qayta login
ESKIZ_TOKEN_TTL_SEC = 60 * 60


def normalize_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('998'):
        return digits
    if digits.startswith('0') and len(digits) == 10:
        return '998' + digits[1:]
    if len(digits) == 9:
        return '998' + digits
    return digits


def format_otp_message(code: str) -> str:
    """Eskizda tasdiqlangan matn — faqat kod o‘rinini almashtiramiz."""
    template = (getattr(settings, 'ESKIZ_OTP_TEMPLATE', '') or DEFAULT_OTP_TEMPLATE).strip()
    if '{code}' in template:
        return template.format(code=code)
    if '0000' in template:
        return template.replace('0000', str(code), 1)
    return f'{template} {code}'.strip()


def _credentials() -> tuple[str, str, str]:
    email = (getattr(settings, 'ESKIZ_EMAIL', '') or '').strip()
    password = (getattr(settings, 'ESKIZ_PASSWORD', '') or '').strip()
    from_nick = (getattr(settings, 'ESKIZ_FROM', '') or '4546').strip() or '4546'
    return email, password, from_nick


def _fetch_token(email: str, password: str) -> str:
    """Official API: multipart/form-data email + password (API secret)."""
    resp = requests.post(
        ESKIZ_LOGIN_URL,
        data={'email': email, 'password': password},
        timeout=20,
    )
    try:
        body = resp.json()
    except Exception:
        body = {}
    if resp.status_code != 200:
        raise RuntimeError(body.get('message') or f'Eskiz login HTTP {resp.status_code}')
    token = (body.get('data') or {}).get('token')
    if not token:
        raise RuntimeError('Eskiz token olinmadi')
    return token


def get_eskiz_token(*, force_refresh: bool = False) -> str:
    email, password, _ = _credentials()
    if not email or not password:
        raise RuntimeError('ESKIZ_EMAIL / ESKIZ_PASSWORD sozlanmagan')

    if not force_refresh:
        cached = cache.get(ESKIZ_TOKEN_CACHE_KEY)
        if cached:
            return cached

    token = _fetch_token(email, password)
    cache.set(ESKIZ_TOKEN_CACHE_KEY, token, ESKIZ_TOKEN_TTL_SEC)
    return token


def _sms_accepted(http_status: int, body: dict) -> bool:
    """Eskiz muvaffaqiyat: status=success|waiting yoki id qaytishi."""
    if http_status != 200:
        return False
    status = (body.get('status') or '').lower()
    if status in ('success', 'waiting'):
        return True
    if body.get('id'):
        return True
    data = body.get('data')
    if isinstance(data, dict) and data.get('id'):
        return True
    return False


def send_sms(phone: str, message: str, code: Optional[str] = None) -> dict[str, Any]:
    """
    Eskiz orqali SMS yuborish.
    :return: {'success': bool, 'message': str, 'code': str|None, 'sms_id': ...}
    """
    email, password, from_nick = _credentials()
    phone = normalize_phone(phone)

    if not email or not password:
        return {
            'success': False,
            'message': 'Eskiz sozlanmagan. Server .env ga ESKIZ_EMAIL va ESKIZ_PASSWORD (API secret) qo‘ying.',
            'code': code,
        }

    try:
        token = get_eskiz_token()
        headers = {'Authorization': f'Bearer {token}'}
        payload = {
            'mobile_phone': phone,
            'message': message,
            'from': from_nick,
        }
        sms_resp = requests.post(ESKIZ_SEND_URL, headers=headers, data=payload, timeout=20)

        # Token eskirgan bo‘lsa — qayta login
        if sms_resp.status_code == 401:
            cache.delete(ESKIZ_TOKEN_CACHE_KEY)
            token = get_eskiz_token(force_refresh=True)
            headers = {'Authorization': f'Bearer {token}'}
            sms_resp = requests.post(ESKIZ_SEND_URL, headers=headers, data=payload, timeout=20)

        try:
            body = sms_resp.json()
        except Exception:
            body = {}

        if _sms_accepted(sms_resp.status_code, body):
            sms_id = body.get('id')
            if not sms_id and isinstance(body.get('data'), dict):
                sms_id = body['data'].get('id')
            logger.info('Eskiz SMS ok phone=%s id=%s status=%s', phone, sms_id, body.get('status'))
            return {
                'success': True,
                'message': 'СМС отправлено',
                'code': code,
                'sms_id': sms_id,
            }

        eskiz_msg = body.get('message') or body.get('error') or sms_resp.text[:300]
        logger.warning('Eskiz SMS fail phone=%s http=%s msg=%s', phone, sms_resp.status_code, eskiz_msg)
        result = {'success': False, 'message': str(eskiz_msg), 'code': None}
        if settings.DEBUG and code:
            result['code'] = code
        return result

    except Exception as e:
        logger.exception('Eskiz SMS exception phone=%s', phone)
        return {
            'success': False,
            'message': str(e),
            'code': code if settings.DEBUG else None,
        }


def send_otp_sms(phone: str, code: str) -> dict[str, Any]:
    """Login OTP — tasdiqlangan Eskiz shabloni bilan."""
    return send_sms(phone, format_otp_message(code), code)
