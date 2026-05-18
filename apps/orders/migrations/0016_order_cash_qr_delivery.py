from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0015_alter_orderproduct_quantity'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='cash_qr_token',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                null=True,
                unique=True,
                verbose_name='Cash QR token',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='qr_confirmed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='QR tasdiqlangan vaqt'),
        ),
        migrations.AddField(
            model_name='order',
            name='delivered_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Yetkazilgan vaqt'),
        ),
        migrations.AddField(
            model_name='order',
            name='customer_delivery_accepted',
            field=models.BooleanField(blank=True, null=True, verbose_name='Mijoz qabul qildi'),
        ),
        migrations.AddField(
            model_name='order',
            name='customer_delivery_responded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Mijoz javobi vaqti'),
        ),
    ]
