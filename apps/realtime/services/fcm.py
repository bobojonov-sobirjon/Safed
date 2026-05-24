"""Firebase FCM credential loading and send helpers."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_app_initialized = False
_auth_failed = False


def firebase_credentials_status() -> Dict[str, Any]:
    """Diagnostika: production .env / JSON fayl to‘g‘rimi."""
    cred_file = (getattr(settings, 'FIREBASE_CREDENTIALS_FILE', '') or '').strip()
    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or ''
    client_email = getattr(settings, 'FIREBASE_CLIENT_EMAIL', '') or ''
    private_key = getattr(settings, 'FIREBASE_PRIVATE_KEY', '') or ''
    issues: List[str] = []

    if cred_file:
        if not os.path.isfile(cred_file):
            issues.append(f'FIREBASE_CREDENTIALS_FILE topilmadi: {cred_file}')
    else:
        if not project_id:
            issues.append('FIREBASE_PROJECT_ID bo‘sh')
        if not client_email:
            issues.append('FIREBASE_CLIENT_EMAIL bo‘sh')
        if not private_key:
            issues.append('FIREBASE_PRIVATE_KEY bo‘sh')
        elif 'BEGIN PRIVATE KEY' not in private_key:
            issues.append(
                "FIREBASE_PRIVATE_KEY noto'g'ri format (\\n yoki qo'shtirnoq muammosi). "
                'JSON fayl ishlatish tavsiya: FIREBASE_CREDENTIALS_FILE=/path/serviceAccount.json'
            )

    return {
        'credentials_file': cred_file or None,
        'project_id': project_id or None,
        'client_email': client_email or None,
        'private_key_ok': bool(private_key and 'BEGIN PRIVATE KEY' in private_key),
        'issues': issues,
    }


def _load_firebase_certificate():
    import firebase_admin
    from firebase_admin import credentials

    cred_file = (getattr(settings, 'FIREBASE_CREDENTIALS_FILE', '') or '').strip()
    if cred_file:
        if not os.path.isfile(cred_file):
            raise FileNotFoundError(f'FIREBASE_CREDENTIALS_FILE not found: {cred_file}')
        return credentials.Certificate(cred_file)

    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or ''
    client_email = getattr(settings, 'FIREBASE_CLIENT_EMAIL', '') or ''
    private_key = getattr(settings, 'FIREBASE_PRIVATE_KEY', '') or ''
    if not (project_id and client_email and private_key):
        raise ValueError('Firebase credentials incomplete in .env')

    cred_dict = {
        'type': 'service_account',
        'project_id': project_id,
        'private_key_id': getattr(settings, 'FIREBASE_PRIVATE_KEY_ID', '') or '',
        'private_key': private_key,
        'client_email': client_email,
        'client_id': str(getattr(settings, 'FIREBASE_CLIENT_ID', '') or ''),
        'auth_uri': getattr(
            settings,
            'FIREBASE_AUTH_URI',
            'https://accounts.google.com/o/oauth2/auth',
        ),
        'token_uri': getattr(settings, 'FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
        'auth_provider_x509_cert_url': getattr(
            settings,
            'FIREBASE_AUTH_PROVIDER_CERT_URL',
            'https://www.googleapis.com/oauth2/v1/certs',
        ),
        'client_x509_cert_url': getattr(settings, 'FIREBASE_CLIENT_CERT_URL', '') or '',
    }
    return credentials.Certificate(cred_dict)


def _ensure_firebase_app() -> bool:
    global _app_initialized, _auth_failed
    if _auth_failed:
        return False
    if _app_initialized:
        return True

    status = firebase_credentials_status()
    if status['issues']:
        logger.error('Firebase config issues: %s', '; '.join(status['issues']))
        return False

    try:
        import firebase_admin
    except ImportError:
        logger.warning('firebase-admin not installed; skip FCM')
        return False

    if firebase_admin._apps:
        _app_initialized = True
        return True

    try:
        cred = _load_firebase_certificate()
        firebase_admin.initialize_app(cred)
        _app_initialized = True
        return True
    except Exception:
        logger.exception('Firebase init failed')
        return False


def verify_fcm_api_access() -> Dict[str, Any]:
    """
    Init yetarli emas — FCM HTTP API ga haqiqiy so‘rov (dry_run).
    401 bu yerda: kalit yoki Cloud Messaging API muammosi.
    InvalidArgument (yomon test token) = auth OK.
    """
    if not _ensure_firebase_app():
        return {
            'ok': False,
            'stage': 'init',
            'detail': 'Firebase Admin SDK init muvaffaqiyatsiz',
        }

    from firebase_admin import messaging

    dummy_token = 'dryrun' + ('x' * 140)
    try:
        message = messaging.Message(
            notification=messaging.Notification(title='FCM test', body='FCM test'),
            token=dummy_token,
        )
        messaging.send(message, dry_run=True)
        return {'ok': True, 'stage': 'fcm_api', 'detail': 'FCM API auth muvaffaqiyatli (dry_run)'}
    except Exception as exc:
        if _is_auth_error(exc):
            return {
                'ok': False,
                'stage': 'fcm_api',
                'error': 'auth_401',
                'detail': str(exc),
                'fix': (
                    'Google Cloud Console → safed-operator → APIs → '
                    '"Firebase Cloud Messaging API" yoqing. '
                    'Yangi service account JSON: FIREBASE_CREDENTIALS_FILE=...'
                ),
            }
        exc_name = type(exc).__name__
        msg = str(exc).lower()
        if exc_name == 'InvalidArgumentError' or 'registration token' in msg:
            return {
                'ok': True,
                'stage': 'fcm_api',
                'detail': 'FCM API auth OK (test token rad etildi — bu normal)',
            }
        return {
            'ok': False,
            'stage': 'fcm_api',
            'error': exc_name,
            'detail': str(exc),
        }


def _deactivate_device_token(token: str) -> None:
    from apps.accounts.models import UserDevice

    count = UserDevice.objects.filter(device_token=token, is_active=True).update(is_active=False)
    if count:
        logger.info('FCM: deactivated invalid device token=%s…', token[:12])


def _is_obviously_invalid_token(token: str) -> bool:
    value = (token or '').strip()
    if len(value) < 20:
        return True
    return value.lower() in {'string', 'test', 'token', 'fcm_token', 'device_token'}


def _is_auth_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    return name in {'ThirdPartyAuthError', 'UnauthenticatedError'}


def send_fcm_to_tokens(
    tokens: Iterable[str],
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> int:
    """Send push to device tokens. Returns count of successful sends."""
    token_list: List[str] = [t for t in tokens if t]
    if not token_list:
        return 0
    if not _ensure_firebase_app():
        return 0

    from firebase_admin import exceptions as firebase_exceptions
    from firebase_admin import messaging

    payload_data = {str(k): str(v) for k, v in (data or {}).items()}
    success = 0
    global _auth_failed

    for token in token_list:
        if _is_obviously_invalid_token(token):
            logger.warning('FCM: skip invalid placeholder token=%s…', token[:12])
            _deactivate_device_token(token)
            continue
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=payload_data,
                token=token,
            )
            messaging.send(message)
            success += 1
        except firebase_exceptions.NotFoundError:
            logger.warning('FCM: unregistered token=%s…', token[:12])
            _deactivate_device_token(token)
        except firebase_exceptions.InvalidArgumentError:
            logger.warning('FCM: invalid registration token=%s…', token[:12])
            _deactivate_device_token(token)
        except Exception as exc:
            if _is_auth_error(exc):
                _auth_failed = True
                logger.error(
                    'FCM 401: Firebase service account not authorized. '
                    'Production .env da FIREBASE_PRIVATE_KEY yoki FIREBASE_CREDENTIALS_FILE '
                    'ni tekshiring. Firebase Console → Service accounts → yangi JSON yuklab oling. '
                    'Google Cloud da "Firebase Cloud Messaging API" yoqilgan bo‘lishi kerak. '
                    'Mobil ilova project_id=%s bilan bir xil bo‘lishi kerak.',
                    getattr(settings, 'FIREBASE_PROJECT_ID', ''),
                )
                break
            logger.exception('FCM send failed token=%s…', token[:12])
    return success
