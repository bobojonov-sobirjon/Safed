"""Default Super Admin yaratish: phone=123456789, password=123456789admin@#"""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from apps.accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Default Super Admin (phone=123456789, password=123456789admin@#)'

    def handle(self, *args, **options):
        phone = '123456789'
        password = '123456789admin@#'
        user, created = CustomUser.objects.update_or_create(
            phone=phone,
            defaults={
                'username': phone,
                'is_admin': True,
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
            }
        )
        user.set_password(password)
        user.save()

        group, _ = Group.objects.get_or_create(name='Super Admin')
        user.groups.add(group)

        self.stdout.write(self.style.SUCCESS(f'Super Admin {"yaratildi" if created else "yangilandi"}: {phone}'))
