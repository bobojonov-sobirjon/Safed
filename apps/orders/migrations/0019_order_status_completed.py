# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0018_min_order_subtotal_1000'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('created', 'Created'),
                    ('confirmed', 'Confirmed'),
                    ('picking', 'Picking'),
                    ('shipped', 'Shipped'),
                    ('delivered', 'Delivered'),
                    ('completed', 'Completed'),
                    ('rejected', 'Rejected'),
                    ('cancelled', 'Cancelled (user)'),
                ],
                db_index=True,
                default='created',
                max_length=20,
                verbose_name='Статус',
            ),
        ),
    ]
