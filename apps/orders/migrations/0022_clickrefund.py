from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0021_geo_coordinates_18_decimals'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClickRefund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Qaytarilgan summa')),
                ('click_payment_id', models.BigIntegerField(db_index=True, verbose_name='CLICK payment_id (API)')),
                (
                    'state',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('processing', 'Processing'),
                            ('completed', 'Completed'),
                            ('failed', 'Failed'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('idempotency_key', models.CharField(max_length=128, unique=True, verbose_name='Idempotency key')),
                ('error_code', models.IntegerField(blank=True, null=True)),
                ('error_note', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='click_refunds',
                        to='orders.order',
                        verbose_name='Заказ',
                    ),
                ),
                (
                    'source_payment',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='refunds',
                        to='orders.clickpayment',
                        verbose_name='CLICK to‘lov',
                    ),
                ),
            ],
            options={
                'verbose_name': 'CLICK qaytarish',
                'verbose_name_plural': 'CLICK qaytarishlar',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['order', '-created_at'], name='orders_clic_order_i_4a8b2d_idx'),
                ],
            },
        ),
    ]
