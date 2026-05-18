from decimal import Decimal

from django.db import migrations, models


def forwards_product_units(apps, schema_editor):
    Products = apps.get_model('products', 'Products')
    for p in Products.objects.all().iterator():
        unit = 'kg' if getattr(p, 'sale_unit', None) == 'weight' else 'piece'
        sale = 'weight' if unit == 'kg' else 'piece'
        Products.objects.filter(pk=p.pk).update(
            product_unit=unit,
            unit_amount=Decimal('1'),
            sale_unit=sale,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_korzinka_checkout_v1'),
    ]

    operations = [
        migrations.AddField(
            model_name='products',
            name='product_unit',
            field=models.CharField(
                choices=[
                    ('piece', 'Piece'),
                    ('kg', 'Kilogram'),
                    ('gram', 'Gram'),
                    ('liter', 'Liter'),
                    ('ml', 'Milliliter'),
                ],
                db_index=True,
                default='piece',
                help_text='Цена в price за unit_amount этой единицы (kg, ml, piece, …).',
                max_length=16,
                verbose_name='Единица цены',
            ),
        ),
        migrations.AddField(
            model_name='products',
            name='unit_amount',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('1'),
                help_text='Напр. 1 (кг), 500 (ml для бутылки 500ml). total = (normalized_qty / unit_amount) × price.',
                max_digits=12,
                verbose_name='Базовый объём цены',
            ),
        ),
        migrations.RunPython(forwards_product_units, migrations.RunPython.noop),
    ]
