from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_order_payment_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClickPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Сумма')),
                ('click_trans_id', models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name='CLICK trans id')),
                ('click_paydoc_id', models.BigIntegerField(blank=True, null=True, verbose_name='CLICK paydoc id')),
                (
                    'state',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('prepared', 'Prepared'),
                            ('completed', 'Completed'),
                            ('cancelled', 'Cancelled'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('last_error_code', models.IntegerField(blank=True, null=True)),
                ('last_error_note', models.CharField(blank=True, default='', max_length=255)),
                ('prepared_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='click_payments',
                        to='orders.order',
                        verbose_name='Заказ',
                    ),
                ),
            ],
            options={
                'verbose_name': 'CLICK платёж',
                'verbose_name_plural': 'CLICK платежи',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['order', '-created_at'], name='orders_clic_order_i_idx')],
            },
        ),
    ]
