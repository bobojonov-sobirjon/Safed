# Generated manually
from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ['User', 'Super Admin', 'Admin', 'Operator', 'Courier']:
        Group.objects.get_or_create(name=name)


def reverse_func(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['User', 'Super Admin', 'Admin', 'Operator', 'Courier']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_phoneotp_is_admin'),
    ]

    operations = [
        migrations.RunPython(create_groups, reverse_func),
    ]
