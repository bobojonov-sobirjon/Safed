"""Qo‘lda tekshirish: python manage.py send_daily_cart_reminder"""
from django.core.management.base import BaseCommand

from apps.realtime.services.marketing_push import send_daily_cart_reminder_to_all


class Command(BaseCommand):
    help = 'Barcha faol FCM qurilmalarga kunlik savat eslatmasi push yuboradi (o‘zbekcha).'

    def handle(self, *args, **options):
        result = send_daily_cart_reminder_to_all()
        self.stdout.write(self.style.SUCCESS(str(result)))
