"""Tek push: python manage.py send_test_push --user-id 8"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import UserDevice
from apps.realtime.services.fcm import send_fcm_to_tokens, verify_fcm_api_access

User = get_user_model()


class Command(BaseCommand):
    help = 'Bitta user yoki barcha faol tokenlarga test FCM push yuboradi.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, help='Faqat shu user id uchun')
        parser.add_argument('--all', action='store_true', help='Barcha faol tokenlar')

    def handle(self, *args, **options):
        api = verify_fcm_api_access()
        if not api.get('ok'):
            self.stdout.write(self.style.ERROR(f"FCM API: {api}"))
            return

        if options.get('user_id'):
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
            self.stdout.write(self.style.ERROR('--user-id N yoki --all kerak'))
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
            self.stdout.write(
                self.style.WARNING(
                    'Yuborilmadi: logda FCM 401 yoki token boshqa Firebase project dan. '
                    'Mobil google-services.json project_id = safed-operator bo‘lishi kerak.',
                ),
            )
