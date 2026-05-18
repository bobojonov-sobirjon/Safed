from django.db import migrations, models
import django.db.models.deletion
import parler.fields
import parler.models


CANCEL_REASON_ROWS = [
    (
        'changed_mind',
        10,
        {'uz': 'Fikrim o‘zgardi', 'ru': 'Передумал', 'en': 'Changed my mind'},
    ),
    (
        'wrong_address',
        20,
        {'uz': 'Noto‘g‘ri manzil', 'ru': 'Неверный адрес', 'en': 'Wrong address'},
    ),
    (
        'long_delivery',
        30,
        {'uz': 'Yetkazish juda uzoq', 'ru': 'Долгая доставка', 'en': 'Delivery takes too long'},
    ),
    (
        'ordered_by_mistake',
        40,
        {'uz': 'Xato buyurtma qildim', 'ru': 'Заказал(а) по ошибке', 'en': 'Ordered by mistake'},
    ),
    (
        'found_cheaper',
        50,
        {'uz': 'Boshqa joyda arzonroq', 'ru': 'Нашёл дешевле', 'en': 'Found a better price'},
    ),
    (
        'payment_issue',
        60,
        {'uz': 'To‘lov bilan muammo', 'ru': 'Проблема с оплатой', 'en': 'Payment issue'},
    ),
]


def seed_cancel_reasons(apps, schema_editor):
    conn = schema_editor.connection
    master_table = 'orders_ordercancelreason'
    trans_table = 'orders_ordercancelreason_translation'
    with conn.cursor() as cursor:
        for code, sort_order, names in CANCEL_REASON_ROWS:
            if conn.vendor == 'postgresql':
                cursor.execute(
                    f'INSERT INTO {master_table} (code, sort_order, is_active) '
                    'VALUES (%s, %s, %s) RETURNING id',
                    [code, sort_order, True],
                )
                reason_id = cursor.fetchone()[0]
            else:
                cursor.execute(
                    f'INSERT INTO {master_table} (code, sort_order, is_active) VALUES (%s, %s, %s)',
                    [code, sort_order, True],
                )
                reason_id = cursor.lastrowid
            for lang, name in names.items():
                cursor.execute(
                    f'INSERT INTO {trans_table} (language_code, name, master_id) VALUES (%s, %s, %s)',
                    [lang, name, reason_id],
                )


def unseed_cancel_reasons(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM orders_ordercancelreason')


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0013_orderproduct_product_unit'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderCancelReason',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=50, unique=True, verbose_name='Код')),
                ('sort_order', models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Активна')),
            ],
            options={
                'verbose_name': 'Причина отмены',
                'verbose_name_plural': 'Причины отмены',
                'ordering': ['sort_order', 'id'],
            },
            bases=(parler.models.TranslatableModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='OrderCancelReasonTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language_code', models.CharField(db_index=True, max_length=15, verbose_name='Language')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                (
                    'master',
                    parler.fields.TranslationsForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='translations',
                        to='orders.ordercancelreason',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Причина отмены Translation',
                'db_table': 'orders_ordercancelreason_translation',
                'db_tablespace': '',
                'managed': True,
                'default_permissions': (),
            },
            bases=(parler.models.TranslatedFieldsModelMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='ordercancelreasontranslation',
            unique_together={('language_code', 'master')},
        ),
        migrations.AddField(
            model_name='order',
            name='cancel_comment',
            field=models.TextField(blank=True, default='', verbose_name='Комментарий при отмене'),
        ),
        migrations.AddField(
            model_name='order',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Время отмены'),
        ),
        migrations.AddField(
            model_name='order',
            name='cancel_reasons',
            field=models.ManyToManyField(
                blank=True,
                related_name='orders',
                to='orders.ordercancelreason',
                verbose_name='Причины отмены',
            ),
        ),
        migrations.RunPython(seed_cancel_reasons, unseed_cancel_reasons),
    ]
