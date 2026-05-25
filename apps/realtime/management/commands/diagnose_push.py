"""Push diagnostika: python manage.py diagnose_push"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import UserDevice
from apps.core.enums import UserGroup
from apps.realtime.services.fcm import _ensure_firebase_app, firebase_credentials_status
from apps.realtime.services.order_notifications import _new_order_push_recipient_ids

User = get_user_model()


class Command(BaseCommand):
    help = 'Operator/Kuryer push: guruh, device token, Firebase holati.'

    def handle(self, *args, **options):
        fb = firebase_credentials_status()
        self.stdout.write('=== Firebase ===')
        self.stdout.write(f"  project_id: {fb.get('project_id')}")
        self.stdout.write(f"  private_key_ok: {fb.get('private_key_ok')}")
        if fb.get('issues'):
            for i in fb['issues']:
                self.stdout.write(self.style.ERROR(f'  ! {i}'))
        else:
            ok = _ensure_firebase_app()
            self.stdout.write(self.style.SUCCESS(f'  init: {ok}'))

        self.stdout.write('')
        self.stdout.write('=== Yangi buyurtma push (Operator + Admin + Super Admin) ===')
        for uid in _new_order_push_recipient_ids():
            u = User.objects.get(pk=uid)
            groups = list(u.groups.values_list('name', flat=True))
            tokens = UserDevice.objects.filter(user_id=uid, is_active=True).exclude(device_token='').count()
            line = f"  id={uid} phone={u.phone} groups={groups} fcm_devices={tokens}"
            if tokens:
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stdout.write(self.style.WARNING(line + '  ← PUSH KELMAYDI (token yo‘q)'))

        if not _new_order_push_recipient_ids():
            self.stdout.write(self.style.ERROR('  Hech kim topilmadi — Operator/Admin/Super Admin guruhiga user qo‘shing'))

        self.stdout.write('')
        self.stdout.write('=== Kuryerlar (push faqat add-courier da) ===')
        couriers = User.objects.filter(is_active=True, groups__name=UserGroup.COURIER.value).distinct()
        for u in couriers:
            tokens = UserDevice.objects.filter(user_id=u.pk, is_active=True).exclude(device_token='').count()
            line = f"  id={u.pk} phone={u.phone} fcm_devices={tokens}"
            self.stdout.write(self.style.WARNING(line) if not tokens else line)

        self.stdout.write('')
        self.stdout.write('Eslatma:')
        self.stdout.write('  • Operator push — POST /orders/ yaratilganda')
        self.stdout.write('  • Kuryer push — faqat POST /orders/{id}/add-courier/')
        self.stdout.write('  • Mobil: POST /api/v1/devices/ { device_token, device_type }')
