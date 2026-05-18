from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0016_order_cash_qr_delivery'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='cash_qr_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='orders/cash_qr/',
                verbose_name='Cash QR rasm (PNG)',
            ),
        ),
    ]
