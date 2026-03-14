# Generated manually
import django.db.models.deletion
import parler.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('categories', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Badge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активный')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
            ],
            options={
                'verbose_name': 'Бейдж',
                'verbose_name_plural': 'Бейджи',
            },
        ),
        migrations.CreateModel(
            name='Unit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активный')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
            ],
            options={
                'verbose_name': 'Единица измерения',
                'verbose_name_plural': 'Единицы измерения',
            },
        ),
        migrations.CreateModel(
            name='Products',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unique_id', models.CharField(blank=True, max_length=255, null=True, verbose_name='Уникальный ID')),
                ('quantity', models.PositiveIntegerField(default=0, verbose_name='Количество')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена')),
                ('price_discount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Скидка')),
                ('discount_percentage', models.PositiveIntegerField(blank=True, default=0, null=True, verbose_name='Процент скидки')),
                ('is_discount', models.BooleanField(default=False, verbose_name='Скидка')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активный')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('badge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='products', to='products.badge', verbose_name='Бейдж')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='categories.category', verbose_name='Категория')),
                ('unit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='products', to='products.unit', verbose_name='Единица измерения')),
            ],
            options={
                'verbose_name': 'Продукт',
                'verbose_name_plural': 'Продукты',
                'ordering': ['-created_at'],
            },
            bases=(parler.models.TranslatableModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ProductsTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language_code', models.CharField(db_index=True, max_length=15, verbose_name='Language')),
                ('name', models.CharField(blank=True, max_length=255, null=True, verbose_name='Название')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Описание')),
                ('composition', models.TextField(blank=True, null=True, verbose_name='Состав')),
                ('expiration_date', models.DateField(blank=True, null=True, verbose_name='Срок годности')),
                ('country', models.CharField(blank=True, max_length=255, null=True, verbose_name='Страна')),
                ('grammage', models.CharField(blank=True, max_length=255, null=True, verbose_name='Граммаж')),
                ('master', parler.fields.TranslationsForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='translations', to='products.products')),
            ],
            options={
                'verbose_name': 'Продукт Translation',
                'db_table': 'products_products_translation',
                'db_tablespace': '',
                'managed': True,
                'default_permissions': (),
            },
            bases=(parler.models.TranslatedFieldsModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ProductBarcode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('barcode', models.CharField(max_length=255, verbose_name='Штрихкод')),
                ('barcode_image', models.ImageField(blank=True, null=True, upload_to='barcodes/images/', verbose_name='Изображение штрихкода')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активный')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='barcodes', to='products.products', verbose_name='Продукт')),
            ],
            options={
                'verbose_name': 'Штрихкод продукта',
                'verbose_name_plural': 'Штрихкоды продуктов',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(blank=True, null=True, upload_to='products/images/', verbose_name='Изображение')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активный')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='products.products', verbose_name='Продукт')),
            ],
            options={
                'verbose_name': 'Изображение продукта',
                'verbose_name_plural': 'Изображения продуктов',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProductSavedUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активный')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='savings', to='products.products', verbose_name='Продукт')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='savings', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Сохраненный продукт',
                'verbose_name_plural': 'Сохраненные продукты',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='products',
            index=models.Index(fields=['is_active'], name='products_pr_is_acti_4a8e2f_idx'),
        ),
        migrations.AddIndex(
            model_name='productbarcode',
            index=models.Index(fields=['product'], name='products_pr_product_d7f36a_idx'),
        ),
        migrations.AddIndex(
            model_name='productbarcode',
            index=models.Index(fields=['is_active'], name='products_pr_is_acti_b8d8b1_idx'),
        ),
        migrations.AddIndex(
            model_name='productimage',
            index=models.Index(fields=['product'], name='products_pr_product_2c4a3e_idx'),
        ),
        migrations.AddIndex(
            model_name='productimage',
            index=models.Index(fields=['is_active'], name='products_pr_is_acti_9f2c4d_idx'),
        ),
        migrations.AddIndex(
            model_name='productsaveduser',
            index=models.Index(fields=['product'], name='products_pr_product_8a5f2e_idx'),
        ),
        migrations.AddIndex(
            model_name='productsaveduser',
            index=models.Index(fields=['user'], name='products_pr_user_id_3c1a4d_idx'),
        ),
        migrations.AddIndex(
            model_name='productsaveduser',
            index=models.Index(fields=['is_active'], name='products_pr_is_acti_1e9b2a_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='productstranslation',
            unique_together={('language_code', 'master')},
        ),
    ]
