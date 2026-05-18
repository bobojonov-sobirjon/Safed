from decimal import Decimal
from django.db import migrations, models


def copy_quantity_to_ordered(apps, schema_editor):
    OrderProduct = apps.get_model('orders', 'OrderProduct')
    for op in OrderProduct.objects.all().iterator():
        if op.ordered_quantity is None:
            op.ordered_quantity = op.quantity
            op.save(update_fields=['ordered_quantity'])


def backfill_original_totals(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for o in Order.objects.filter(original_estimated_total__isnull=True).iterator():
        o.original_estimated_total = o.estimated_total
        if o.payment_status == 'paid' and o.paid_amount is None:
            o.paid_amount = o.estimated_total
        o.save(update_fields=['original_estimated_total', 'paid_amount'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_rename_orders_clic_order_i_idx_orders_clic_order_i_bd019e_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='original_estimated_total',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                verbose_name='Сумма при оформлении',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='paid_amount',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                verbose_name='Оплачено клиентом',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='adjustment_balance',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('0.00'), max_digits=14,
                verbose_name='Разница после yig‘ish (+ доплата, − возврат)',
            ),
        ),
        migrations.AlterField(
            model_name='order',
            name='final_total',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                verbose_name='Итог после yig‘ish',
            ),
        ),
        migrations.AddField(
            model_name='orderproduct',
            name='ordered_quantity',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=12, null=True,
                verbose_name='Заказано при оформлении',
            ),
        ),
        migrations.RunPython(copy_quantity_to_ordered, migrations.RunPython.noop),
        migrations.RunPython(backfill_original_totals, migrations.RunPython.noop),
    ]
