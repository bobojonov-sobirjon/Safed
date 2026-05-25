"""Firebase FCM credential loading and send helpers."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_app_initialized = False
_auth_failed = False

FCM_MESSAGING_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'


def reset_fcm_auth_state() -> None:
    """401 dan keyin qayta tekshirish (manage.py buyruqlari uchun)."""
    global _app_initialized, _auth_failed
    _auth_failed = False
    _app_initialized = False
    try:
        import firebase_admin
        if firebase_admin._apps:
            firebase_admin.delete_app(firebase_admin.get_app())
    except Exception:
        pass


def build_firebase_cred_dict() -> Dict[str, str]:
    """Service account dict — faqat `.env` (JSON faylsiz)."""
    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or ''
    client_email = getattr(settings, 'FIREBASE_CLIENT_EMAIL', '') or ''
    private_key = getattr(settings, 'FIREBASE_PRIVATE_KEY', '') or ''
    if not (project_id and client_email and private_key):
        raise ValueError('Firebase credentials incomplete in .env')

    cred_dict: Dict[str, str] = {
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
    universe = getattr(settings, 'FIREBASE_UNIVERSE_DOMAIN', '') or ''
    if universe:
        cred_dict['universe_domain'] = universe
    return cred_dict


def firebase_credentials_status() -> Dict[str, Any]:
    """Diagnostika: production .env / JSON fayl to‘g‘rimi."""
    cred_file = (getattr(settings, 'FIREBASE_CREDENTIALS_FILE', '') or '').strip()
    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or ''
    client_email = getattr(settings, 'FIREBASE_CLIENT_EMAIL', '') or ''
    private_key = getattr(settings, 'FIREBASE_PRIVATE_KEY', '') or ''
    issues: List[str] = []
    source = 'env'

    if cred_file:
        source = 'file'
        if not os.path.isfile(cred_file):
            issues.append(f'FIREBASE_CREDENTIALS_FILE topilmadi: {cred_file}')
    if not project_id:
        issues.append('FIREBASE_PROJECT_ID bo‘sh')
    if not client_email:
        issues.append('FIREBASE_CLIENT_EMAIL bo‘sh')
    if not private_key:
        issues.append('FIREBASE_PRIVATE_KEY bo‘sh')
    elif 'BEGIN PRIVATE KEY' not in private_key or 'END PRIVATE KEY' not in private_key:
        issues.append(
            "FIREBASE_PRIVATE_KEY noto'g'ri — systemd/.env da qator uzilib qolgan. "
            'Bir qatorda \\n bilan yozing yoki kalitni qayta nusxalang.'
        )
    elif len(private_key) < 1500:
        issues.append(
            f'FIREBASE_PRIVATE_KEY juda qisqa (len={len(private_key)}); '
            'to‘liq kalit ~1700 belgi bo‘lishi kerak.'
        )

    return {
        'credentials_file': cred_file or None,
        'credentials_source': source,
        'project_id': project_id or None,
        'client_email': client_email or None,
        'private_key_ok': bool(
            private_key
            and 'BEGIN PRIVATE KEY' in private_key
            and 'END PRIVATE KEY' in private_key
            and len(private_key) >= 1500,
        ),
        'private_key_length': len(private_key),
        'private_key_newlines': private_key.count('\n') if private_key else 0,
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

    return credentials.Certificate(build_firebase_cred_dict())


def verify_firebase_oauth() -> Dict[str, Any]:
    """
    Haqiqiy OAuth token (.env private key to‘g‘rimi).
    dry_run o‘tib, send 401 bersa — avval shuni tekshiring.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_info(
            build_firebase_cred_dict(),
            scopes=[FCM_MESSAGING_SCOPE],
        )
        creds.refresh(Request())
        return {
            'ok': True,
            'detail': 'OAuth token olindi — .env service account ishlayapti',
        }
    except Exception as exc:
        return {
            'ok': False,
            'error': type(exc).__name__,
            'detail': str(exc),
            'fix': (
                'FIREBASE_PRIVATE_KEY production .env da buzilgan (uzunlik ~1700, 27 qator). '
                'Google Cloud → safed-operator → APIs → Firebase Cloud Messaging API → Enable. '
                'Firebase Console → Service accounts → kalit bekor qilinmagan bo‘lsin.'
            ),
        }


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
        project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or None
        options = {'projectId': project_id} if project_id else None
        firebase_admin.initialize_app(cred, options=options)
        _app_initialized = True
        return True
    except Exception:
        logger.exception('Firebase init failed')
        return False


def _get_fcm_access_token() -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        build_firebase_cred_dict(),
        scopes=[FCM_MESSAGING_SCOPE],
    )
    creds.refresh(Request())
    return creds.token


def send_fcm_http_v1(
    token: str,
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    validate_only: bool = False,
) -> tuple[int, Dict[str, Any]]:
    """FCM HTTP v1 — aniq HTTP status va JSON xato."""
    import requests

    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or ''
    url = f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'
    message: Dict[str, Any] = {
        'token': token,
        'notification': {'title': title, 'body': body},
    }
    if data:
        message['data'] = {str(k): str(v) for k, v in data.items()}

    access_token = _get_fcm_access_token()
    response = requests.post(
        url,
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json={'validate_only': validate_only, 'message': message},
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {'raw': response.text[:500]}
    return response.status_code, payload


def probe_fcm_http_api() -> Dict[str, Any]:
    """
    Haqiqiy FCM HTTP (dry_run emas).
    403 = API o‘chiq; 400/404 = API ishlayapti; 401 = kalit noto‘g‘ri.
    """
    oauth = verify_firebase_oauth()
    if not oauth.get('ok'):
        return {**oauth, 'stage': 'oauth'}

    probe_token = 'e' * 22 + ':APA91b' + ('A' * 140)
    try:
        status, payload = send_fcm_http_v1(
            probe_token,
            title='FCM probe',
            body='FCM probe',
            validate_only=False,
        )
    except Exception as exc:
        return {'ok': False, 'stage': 'fcm_http', 'error': type(exc).__name__, 'detail': str(exc)}

    err = payload.get('error') or {}
    err_status = (err.get('status') or '').upper()
    err_message = err.get('message') or str(payload)

    if status == 403 or err_status == 'PERMISSION_DENIED':
        return {
            'ok': False,
            'stage': 'fcm_api',
            'error': 'api_disabled',
            'http_status': status,
            'detail': err_message,
            'fix': (
                'Google Cloud Console → loyiha safed-operator → '
                'APIs & Services → Library → "Firebase Cloud Messaging API" → ENABLE. '
                '5–10 daqiqa kuting, keyin qayta urinib ko‘ring.'
            ),
        }
    if status == 401 or err_status == 'UNAUTHENTICATED':
        return {
            'ok': False,
            'stage': 'fcm_api',
            'error': 'auth_401',
            'http_status': status,
            'detail': err_message,
            'fix': 'FIREBASE_PRIVATE_KEY .env da to‘liq (~1700 belgi) yoki yangi service account kalit.',
        }
    if status in (400, 404) or 'registration token' in err_message.lower():
        return {
            'ok': True,
            'stage': 'fcm_api',
            'detail': f'FCM HTTP API ishlayapti (javob {status} — test token rad, bu normal)',
        }
    if status == 200:
        return {'ok': True, 'stage': 'fcm_api', 'detail': 'FCM HTTP 200 OK'}

    return {
        'ok': False,
        'stage': 'fcm_api',
        'error': f'http_{status}',
        'http_status': status,
        'detail': err_message,
    }


def verify_fcm_api_access() -> Dict[str, Any]:
    """Eski nom — haqiqiy HTTP probe."""
    return probe_fcm_http_api()


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


def _parse_fcm_http_error(status: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    err = payload.get('error') or {}
    return {
        'http_status': status,
        'status': (err.get('status') or '').upper(),
        'message': err.get('message') or str(payload),
        'code': err.get('code'),
    }


def send_fcm_to_tokens(
    tokens: Iterable[str],
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> int:
    """FCM HTTP v1 orqali push. Muvaffaqiyatli yuborishlar soni."""
    token_list: List[str] = [t for t in tokens if t]
    if not token_list:
        return 0

    payload_data = {str(k): str(v) for k, v in (data or {}).items()}
    success = 0
    global _auth_failed

    for token in token_list:
        if _auth_failed:
            break
        if _is_obviously_invalid_token(token):
            logger.warning('FCM: skip invalid placeholder token=%s…', token[:12])
            _deactivate_device_token(token)
            continue
        try:
            status, body = send_fcm_http_v1(
                token,
                title=title,
                body=body,
                data=payload_data,
            )
        except Exception as exc:
            logger.exception('FCM HTTP transport failed token=%s…: %s', token[:12], exc)
            continue

        if status == 200:
            success += 1
            continue

        info = _parse_fcm_http_error(status, body)
        msg = info['message']
        err_status = info['status']

        if status == 403 or err_status == 'PERMISSION_DENIED':
            _auth_failed = True
            logger.error(
                'FCM API o‘chiq yoki ruxsat yo‘q (HTTP 403): %s — '
                'Google Cloud → %s → Firebase Cloud Messaging API → ENABLE. '
                'python manage.py check_fcm_config',
                msg,
                getattr(settings, 'FIREBASE_PROJECT_ID', ''),
            )
            break

        if status == 401 or err_status == 'UNAUTHENTICATED':
            _auth_failed = True
            logger.error(
                'FCM auth (HTTP 401): %s — .env FIREBASE_PRIVATE_KEY tekshiring.',
                msg,
            )
            break

        if status == 404 or err_status == 'NOT_FOUND' or 'not registered' in msg.lower():
            logger.warning('FCM: unregistered token=%s… — %s', token[:12], msg[:120])
            _deactivate_device_token(token)
            continue

        if status == 400 or err_status == 'INVALID_ARGUMENT':
            if 'registration token' in msg.lower() or 'senderid' in msg.lower():
                logger.warning(
                    'FCM: token boshqa Firebase project dan bo‘lishi mumkin (%s…): %s',
                    token[:12],
                    msg[:200],
                )
                _deactivate_device_token(token)
                continue

        logger.error('FCM HTTP %s token=%s…: %s', status, token[:12], msg[:300])

    return success
