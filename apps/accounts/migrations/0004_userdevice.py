# Generated manually
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_create_groups'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_token', models.CharField(max_length=512, verbose_name='Token устройства')),
                ('device_type', models.CharField(max_length=50, verbose_name='Тип устройства')),
                ('is_activate', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='devices', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Устройство пользователя',
                'verbose_name_plural': 'Устройства пользователей',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='userdevice',
            index=models.Index(fields=['user'], name='accounts_us_user_id_77e4e0_idx'),
        ),
        migrations.AddIndex(
            model_name='userdevice',
            index=models.Index(fields=['is_activate'], name='accounts_us_is_acti_5c9e36_idx'),
        ),
    ]
