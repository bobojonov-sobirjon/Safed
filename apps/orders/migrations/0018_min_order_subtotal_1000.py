from decimal import Decimal

from django.db import migrations, models


def set_min_order_1000(apps, schema_editor):
    OrderFeeSettings = apps.get_model('orders', 'OrderFeeSettings')
    OrderFeeSettings.objects.filter(pk=1).update(min_order_subtotal=Decimal('1000.00'))


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0017_order_cash_qr_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderfeesettings',
            name='min_order_subtotal',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('1000.00'),
                max_digits=14,
                verbose_name='Мин. сумма товаров для оформления',
            ),
        ),
        migrations.RunPython(set_min_order_1000, migrations.RunPython.noop),
    ]
