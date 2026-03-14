# Generated manually
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lat', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='Широта')),
                ('long', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='Долгота')),
                ('address', models.TextField(blank=True, null=True, verbose_name='Адрес')),
                ('status', models.CharField(choices=[('pending', 'В ожидании'), ('process', 'В обработке'), ('delivering', 'Доставляется'), ('completed', 'Выполнен'), ('rejected', 'Отменён')], default='pending', max_length=20, verbose_name='Статус')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Заказ',
                'verbose_name_plural': 'Заказы',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='OrderProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(verbose_name='Количество')),
                ('total_price', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Сумма')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_products', to='orders.order', verbose_name='Заказ')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_products', to='products.products', verbose_name='Продукт')),
            ],
            options={
                'verbose_name': 'Продукт заказа',
                'verbose_name_plural': 'Продукты заказа',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='OrderCourier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('courier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assigned_orders', to=settings.AUTH_USER_MODEL, verbose_name='Курьер')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_couriers', to='orders.order', verbose_name='Заказ')),
            ],
            options={
                'verbose_name': 'Курьер заказа',
                'verbose_name_plural': 'Курьеры заказов',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['user'], name='orders_order_user_id_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['status'], name='orders_order_status_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='ordercourier',
            unique_together={('order', 'courier')},
        ),
    ]
