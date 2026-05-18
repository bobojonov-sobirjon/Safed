from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_orderfeesettings_hourly_delivery_capacity'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_type',
            field=models.CharField(
                choices=[('card', 'Card'), ('cash', 'Cash')],
                db_index=True,
                default='cash',
                max_length=10,
                verbose_name='Способ оплаты',
            ),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('authorized', 'Authorized'),
                    ('paid', 'Paid'),
                    ('failed', 'Failed'),
                    ('refunded', 'Refunded'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
                verbose_name='Статус оплаты',
            ),
        ),
    ]
