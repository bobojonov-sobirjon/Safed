"""Tek push: python manage.py send_test_push --user-id 8
yoki: python manage.py send_test_push --token 'eCFX...'"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import UserDevice
from django.conf import settings

from apps.realtime.services.fcm import (
    _is_token_project_mismatch,
    _parse_fcm_http_error,
    probe_fcm_real_device_token,
    reset_fcm_auth_state,
    send_fcm_to_tokens,
    verify_firebase_oauth,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Bitta user yoki barcha faol tokenlarga test FCM push yuboradi.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, help='Faqat shu user id uchun')
        parser.add_argument('--token', type=str, help='To‘g‘ridan-to‘g‘ri FCM device token')
        parser.add_argument('--all', action='store_true', help='Barcha faol tokenlar')

    def handle(self, *args, **options):
        reset_fcm_auth_state()
        oauth = verify_firebase_oauth()
        if not oauth.get('ok'):
            self.stdout.write(self.style.ERROR(f"OAuth (.env): {oauth}"))
            self.stdout.write('  python manage.py check_fcm_config')
            return

        if options.get('token'):
            raw = (options['token'] or '').strip()
            if not raw:
                self.stdout.write(self.style.ERROR('--token bo‘sh'))
                return
            tokens = [raw]
        elif options.get('user_id'):
            tokens = list(
                UserDevice.objects.filter(
                    user_id=options['user_id'],
                    is_active=True,
                ).values_list('device_token', flat=True),
            )
            if not tokens:
                self.stdout.write(
                    self.style.WARNING(f"user_id={options['user_id']}: faol token yo‘q"),
                )
                return
        elif options.get('all'):
            tokens = list(
                UserDevice.objects.filter(is_active=True, user__is_active=True)
                .exclude(device_token='')
                .values_list('device_token', flat=True)
                .distinct(),
            )
        else:
            self.stdout.write(self.style.ERROR('--user-id N, --token yoki --all kerak'))
            return

        sent = send_fcm_to_tokens(
            tokens,
            title='Safed test',
            body='Push test — agar ko‘rsangiz, FCM ishlayapti.',
            data={'type': 'test_push', 'event': 'test_push'},
        )
        self.stdout.write(
            self.style.SUCCESS(f'tokens={len(tokens)} sent={sent}'),
        )
        if sent == 0:
            if options.get('user_id'):
                real = probe_fcm_real_device_token(options['user_id'])
            elif options.get('token'):
                from apps.realtime.services.fcm import send_fcm_http_v1, _fcm_authed_session

                session = _fcm_authed_session()
                status, payload = send_fcm_http_v1(
                    tokens[0],
                    title='Safed test',
                    body='Push test',
                    data={'type': 'test_push'},
                    session=session,
                )
                info = _parse_fcm_http_error(status, payload)
                real = {
                    'http_status': status,
                    'detail': info['message'],
                    'token_project_mismatch': info.get('token_project_mismatch'),
                    'fcm_error_codes': info.get('fcm_error_codes'),
                }
                if _is_token_project_mismatch(payload):
                    real['detail'] = (
                        f"{info['message']} "
                        f"(FCM: {info.get('fcm_error_codes') or ['THIRD_PARTY_AUTH_ERROR']})"
                    )
            else:
                real = None
            if real:
                self.stdout.write(self.style.ERROR(f"HTTP {real.get('http_status')}: {real.get('detail')}"))
                if real.get('token_project_mismatch'):
                    self.stdout.write(self.style.ERROR(
                        f"  → Mobil ilova boshqa Firebase loyihadan token berdi. "
                        f"google-services.json project_id = {settings.FIREBASE_PROJECT_ID} bo‘lishi kerak.",
                    ))
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            'Tekshiring: python manage.py check_fcm_config; '
                            "HTTP_PROXY bo'lsa: NO_PROXY=fcm.googleapis.com",
                        ),
                    )
