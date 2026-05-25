"""Production FCM diagnostika: python manage.py check_fcm_config"""
from django.core.management.base import BaseCommand

from apps.realtime.services.fcm import (
    firebase_credentials_status,
    probe_fcm_http_api,
    reset_fcm_auth_state,
    verify_firebase_oauth,
)


class Command(BaseCommand):
    help = 'Firebase FCM (.env) — kalit uzunligi, OAuth, dry_run.'

    def handle(self, *args, **options):
        reset_fcm_auth_state()
        status = firebase_credentials_status()
        self.stdout.write('Firebase FCM (.env):')
        self.stdout.write(f"  source: {status.get('credentials_source')}")
        self.stdout.write(f"  project_id: {status.get('project_id')}")
        self.stdout.write(f"  client_email: {status.get('client_email')}")
        self.stdout.write(f"  credentials_file: {status.get('credentials_file') or '(yo‘q — faqat .env)'}")
        self.stdout.write(f"  private_key_ok: {status.get('private_key_ok')}")
        self.stdout.write(
            f"  private_key_length: {status.get('private_key_length')} "
            f"(kutiladi ~1700, newlines ~27)",
        )
        self.stdout.write(f"  private_key_newlines: {status.get('private_key_newlines')}")

        if status['issues']:
            self.stdout.write(self.style.ERROR('Muammolar:'))
            for issue in status['issues']:
                self.stdout.write(self.style.ERROR(f'  - {issue}'))
            self._print_env_fix()
            return

        self.stdout.write('')
        self.stdout.write('OAuth (haqiqiy token — .env kalit):')
        oauth = verify_firebase_oauth()
        if oauth.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"  {oauth.get('detail')}"))
        else:
            self.stdout.write(self.style.ERROR(f"  {oauth.get('error')}: {oauth.get('detail')}"))
            if oauth.get('fix'):
                self.stdout.write(self.style.WARNING(f"  {oauth.get('fix')}"))
            self._print_api_fix()
            return

        api = probe_fcm_http_api()
        self.stdout.write('')
        self.stdout.write('FCM HTTP API (haqiqiy so‘rov, dry_run emas):')
        if api.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"  {api.get('detail')}"))
            self.stdout.write('')
            self.stdout.write('Keyingi: python manage.py send_test_push --user-id 5')
        else:
            self.stdout.write(self.style.ERROR(f"  {api.get('error')}: {api.get('detail')}"))
            if api.get('fix'):
                self.stdout.write(self.style.WARNING(f"  Tuzatish: {api.get('fix')}"))
            if api.get('error') != 'api_disabled':
                self._print_api_fix()

    def _print_api_fix(self):
        self.stdout.write('')
        self.stdout.write('Google Cloud (loyiha safed-operator):')
        self.stdout.write('  1. APIs & Services → Enable: Firebase Cloud Messaging API')
        self.stdout.write('  2. IAM → firebase-adminsdk-... → Editor yoki Firebase Admin')

    def _print_env_fix(self):
        self.stdout.write('')
        self.stdout.write('Production .env (FIREBASE_PRIVATE_KEY):')
        self.stdout.write('  • Bir qator, ichida \\n (sizdagi format)')
        self.stdout.write('  • systemd: EnvironmentFile=/var/www/Safed/.env')
        self.stdout.write('  • Kalit uzunligi ~1700 bo‘lmasa — qator uzilib qolgan')
        self.stdout.write('  • FIREBASE_CREDENTIALS_FILE bo‘sh qoldiring (faqat .env)')
