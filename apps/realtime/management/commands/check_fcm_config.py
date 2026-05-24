"""Production FCM diagnostika: python manage.py check_fcm_config"""
from django.core.management.base import BaseCommand

from apps.realtime.services.fcm import (
    _ensure_firebase_app,
    firebase_credentials_status,
    verify_fcm_api_access,
)


class Command(BaseCommand):
    help = 'Firebase FCM sozlamalarini tekshiradi (401/auth xatolari uchun).'

    def handle(self, *args, **options):
        status = firebase_credentials_status()
        self.stdout.write('Firebase FCM config:')
        self.stdout.write(f"  project_id: {status.get('project_id')}")
        self.stdout.write(f"  client_email: {status.get('client_email')}")
        self.stdout.write(f"  credentials_file: {status.get('credentials_file')}")
        self.stdout.write(f"  private_key_ok: {status.get('private_key_ok')}")

        if status['issues']:
            self.stdout.write(self.style.ERROR('Muammolar:'))
            for issue in status['issues']:
                self.stdout.write(self.style.ERROR(f'  - {issue}'))
            self._print_json_fix()
            return

        if not _ensure_firebase_app():
            self.stdout.write(self.style.ERROR('Firebase init muvaffaqiyatsiz — loglarni ko‘ring.'))
            return

        self.stdout.write(self.style.SUCCESS('Firebase Admin SDK init: OK'))

        api = verify_fcm_api_access()
        self.stdout.write('')
        self.stdout.write('FCM API tekshiruvi (dry_run):')
        if api.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"  {api.get('detail')}"))
            self.stdout.write('')
            self.stdout.write('Keyingi qadam:')
            self.stdout.write('  python manage.py send_daily_cart_reminder')
            self.stdout.write('')
            self.stdout.write(
                'Agar send 401 bersa — mobil ilova tokeni boshqa Firebase project dan '
                f"({status.get('project_id')} bo'lishi kerak)."
            )
        else:
            self.stdout.write(self.style.ERROR(f"  Xato: {api.get('error')} — {api.get('detail')}"))
            if api.get('fix'):
                self.stdout.write(self.style.WARNING(f"  Tuzatish: {api.get('fix')}"))
            self._print_json_fix()

    def _print_json_fix(self):
        self.stdout.write('')
        self.stdout.write('Tavsiya (production):')
        self.stdout.write('  1. Firebase Console → Project Settings → Service accounts')
        self.stdout.write('  2. "Generate new private key" → JSON fayl')
        self.stdout.write('  3. Serverga: /var/www/Safed/secrets/firebase-safed-operator.json')
        self.stdout.write('  4. .env: FIREBASE_CREDENTIALS_FILE=/var/www/Safed/secrets/firebase-safed-operator.json')
        self.stdout.write('  5. Google Cloud → APIs → "Firebase Cloud Messaging API" → Enable')
