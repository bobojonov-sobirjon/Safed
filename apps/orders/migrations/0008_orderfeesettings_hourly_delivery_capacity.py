from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_korzinka_checkout_v1'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderfeesettings',
            name='hourly_delivery_capacity',
            field=models.PositiveIntegerField(
                default=15,
                help_text='Для сетки GET /busy-slots/?date= и legacy delivery_date/time.',
                verbose_name='Макс. заказов на один часовой интервал доставки',
            ),
        ),
    ]
