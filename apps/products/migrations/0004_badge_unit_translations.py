# Manual migration for Badge and Unit translations
from django.db import migrations, models
import parler.fields


def copy_badge_names_to_translations(apps, schema_editor):
    """Copy existing Badge names to translation table."""
    Badge = apps.get_model('products', 'Badge')
    BadgeTranslation = apps.get_model('products', 'BadgeTranslation')
    
    for badge in Badge.objects.all():
        if hasattr(badge, 'name') and badge.name:
            BadgeTranslation.objects.create(
                master_id=badge.id,
                language_code='ru',
                name=badge.name
            )


def copy_unit_names_to_translations(apps, schema_editor):
    """Copy existing Unit names to translation table."""
    Unit = apps.get_model('products', 'Unit')
    UnitTranslation = apps.get_model('products', 'UnitTranslation')
    
    for unit in Unit.objects.all():
        if hasattr(unit, 'name') and unit.name:
            UnitTranslation.objects.create(
                master_id=unit.id,
                language_code='ru',
                name=unit.name
            )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_alter_badge_options_alter_productsaveduser_options_and_more'),
    ]

    operations = [
        # Create BadgeTranslation table
        migrations.CreateModel(
            name='BadgeTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language_code', models.CharField(db_index=True, max_length=15, verbose_name='Language')),
                ('name', models.CharField(blank=True, max_length=255, null=True, verbose_name='Название')),
                ('master', parler.fields.TranslationsForeignKey(
                    editable=False, 
                    null=True, 
                    on_delete=models.deletion.CASCADE, 
                    related_name='translations', 
                    to='products.badge'
                )),
            ],
            options={
                'verbose_name': 'Бейдж Translation',
                'db_table': 'products_badge_translation',
                'db_tablespace': '',
                'managed': True,
                'default_permissions': (),
                'unique_together': {('language_code', 'master')},
            },
        ),
        
        # Create UnitTranslation table
        migrations.CreateModel(
            name='UnitTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language_code', models.CharField(db_index=True, max_length=15, verbose_name='Language')),
                ('name', models.CharField(blank=True, max_length=255, null=True, verbose_name='Название')),
                ('master', parler.fields.TranslationsForeignKey(
                    editable=False, 
                    null=True, 
                    on_delete=models.deletion.CASCADE, 
                    related_name='translations', 
                    to='products.unit'
                )),
            ],
            options={
                'verbose_name': 'Единица измерения Translation',
                'db_table': 'products_unit_translation',
                'db_tablespace': '',
                'managed': True,
                'default_permissions': (),
                'unique_together': {('language_code', 'master')},
            },
        ),
        
        # Copy existing data to translation tables
        migrations.RunPython(copy_badge_names_to_translations, migrations.RunPython.noop),
        migrations.RunPython(copy_unit_names_to_translations, migrations.RunPython.noop),
        
        # Remove old name fields
        migrations.RemoveField(
            model_name='badge',
            name='name',
        ),
        migrations.RemoveField(
            model_name='unit',
            name='name',
        ),
        
        # Update model options
        migrations.AlterModelOptions(
            name='badge',
            options={'ordering': ['-created_at'], 'verbose_name': 'Бейдж', 'verbose_name_plural': 'Бейджи'},
        ),
        migrations.AlterModelOptions(
            name='unit',
            options={'ordering': ['-created_at'], 'verbose_name': 'Единица измерения', 'verbose_name_plural': 'Единицы измерения'},
        ),
    ]
