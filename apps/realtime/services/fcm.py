"""Firebase Cloud Messaging (FCM) via service account from settings."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_app_initialized = False


def _ensure_firebase_app() -> bool:
    global _app_initialized
    if _app_initialized:
        return True

    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or ''
    client_email = getattr(settings, 'FIREBASE_CLIENT_EMAIL', '') or ''
    private_key = getattr(settings, 'FIREBASE_PRIVATE_KEY', '') or ''
    if not (project_id and client_email and private_key):
        logger.debug('Firebase credentials not configured; skip FCM')
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.warning('firebase-admin not installed; skip FCM')
        return False

    if firebase_admin._apps:
        _app_initialized = True
        return True

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
    try:
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        _app_initialized = True
        return True
    except Exception:
        logger.exception('Firebase init failed')
        return False


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

    from firebase_admin import messaging

    payload_data = {str(k): str(v) for k, v in (data or {}).items()}
    success = 0
    for token in token_list:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=payload_data,
                token=token,
            )
            messaging.send(message)
            success += 1
        except Exception:
            logger.exception('FCM send failed token=%s…', token[:12])
    return success
