from decimal import Decimal

from django.db import migrations, models


def forwards_line_units(apps, schema_editor):
    OrderProduct = apps.get_model('orders', 'OrderProduct')
    Products = apps.get_model('products', 'Products')

    for op in OrderProduct.objects.select_related('product').iterator():
        p = op.product
        if p:
            cat = getattr(p, 'product_unit', None) or (
                'kg' if getattr(p, 'sale_unit', None) == 'weight' else 'piece'
            )
        else:
            cat = 'piece'
        op.product_unit = cat
        op.normalized_quantity = op.quantity
        op.save(update_fields=['product_unit', 'normalized_quantity'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_order_picking_settlement'),
        ('products', '0009_product_unit_and_unit_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderproduct',
            name='product_unit',
            field=models.CharField(
                default='piece',
                help_text='Mijoz yuborgan yoki katalog birligi.',
                max_length=16,
                verbose_name='Единица строки',
            ),
        ),
        migrations.AddField(
            model_name='orderproduct',
            name='normalized_quantity',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text='Katalog product_unit bo‘yicha (narx hisobi uchun).',
                max_digits=12,
                null=True,
                verbose_name='Нормализованное кол-во',
            ),
        ),
        migrations.RunPython(forwards_line_units, migrations.RunPython.noop),
    ]
