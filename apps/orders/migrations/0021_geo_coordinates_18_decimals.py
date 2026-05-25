from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0020_geo_coordinates_precision'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deliveryaddress',
            name='lat',
            field=models.DecimalField(
                blank=True, decimal_places=18, max_digits=21, null=True, verbose_name='Широта',
            ),
        ),
        migrations.AlterField(
            model_name='deliveryaddress',
            name='long',
            field=models.DecimalField(
                blank=True, decimal_places=18, max_digits=21, null=True, verbose_name='Долгота',
            ),
        ),
        migrations.AlterField(
            model_name='order',
            name='lat',
            field=models.DecimalField(
                blank=True, decimal_places=18, max_digits=21, null=True, verbose_name='Широта',
            ),
        ),
        migrations.AlterField(
            model_name='order',
            name='long',
            field=models.DecimalField(
                blank=True, decimal_places=18, max_digits=21, null=True, verbose_name='Долгота',
            ),
        ),
    ]
