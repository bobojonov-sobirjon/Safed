"""
Demo mahsulotlar (Korzinka: turli product_unit).

  python manage.py seed_fake_products --clear
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.categories.models import Category
from apps.core.enums import ProductUnit
from apps.products.models import ProductBarcode, ProductImage, ProductSavedUser, Products
from apps.products.services import ProductService


FAKE_GROCERY_CATEGORY = {
    'translations': {
        'uz': {'name': 'Oziq-ovqat'},
        'ru': {'name': 'Продукты'},
        'en': {'name': 'Groceries'},
    },
    'order': 0,
    'is_active': True,
}

FAKE_PRODUCTS = [
    {
        'translations': {
            'uz': {'name': 'Kartoshka', 'description': 'Yangi kartoshka', 'country': "O'zbekiston"},
            'ru': {'name': 'Картофель', 'description': 'Свежий картофель', 'country': 'Узбекистан'},
            'en': {'name': 'Potatoes', 'description': 'Fresh potatoes', 'country': 'Uzbekistan'},
        },
        'product_unit': ProductUnit.KG.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('12000'),
        'quantity': 800,
        'shelf_location': 'A-01',
    },
    {
        'translations': {
            'uz': {'name': 'Piyoz', 'description': 'Sariq piyoz'},
            'ru': {'name': 'Лук', 'description': 'Репчатый лук'},
            'en': {'name': 'Onion', 'description': 'Yellow onion'},
        },
        'product_unit': ProductUnit.KG.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('9000'),
        'quantity': 600,
        'shelf_location': 'A-02',
    },
    {
        'translations': {
            'uz': {'name': 'Olma', 'description': 'Qizil olma'},
            'ru': {'name': 'Яблоки', 'description': 'Красные яблоки'},
            'en': {'name': 'Apples', 'description': 'Red apples'},
        },
        'product_unit': ProductUnit.KG.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('22000'),
        'quantity': 350,
        'shelf_location': 'B-01',
    },
    {
        'translations': {
            'uz': {'name': 'Banan', 'description': 'Eksport banan'},
            'ru': {'name': 'Бананы', 'description': 'Импортные бананы'},
            'en': {'name': 'Bananas', 'description': 'Import bananas'},
        },
        'product_unit': ProductUnit.KG.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('28000'),
        'quantity': 200,
        'shelf_location': 'B-02',
    },
    {
        'translations': {
            'uz': {'name': 'Sut 1L', 'description': 'Pasterlangan sut'},
            'ru': {'name': 'Молоко 1л', 'description': 'Пастеризованное молоко'},
            'en': {'name': 'Milk 1L', 'description': 'Pasteurized milk'},
        },
        'product_unit': ProductUnit.LITER.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('14000'),
        'quantity': 120,
        'shelf_location': 'C-01',
    },
    {
        'translations': {
            'uz': {'name': 'Cola 0.5L', 'description': 'Sovuq ichimlik'},
            'ru': {'name': 'Cola 0.5л', 'description': 'Газированный напиток'},
            'en': {'name': 'Cola 0.5L', 'description': 'Soft drink'},
        },
        'product_unit': ProductUnit.ML.value,
        'unit_amount': Decimal('500'),
        'price': Decimal('8000'),
        'quantity': 240,
        'shelf_location': 'D-01',
    },
    {
        'translations': {
            'uz': {'name': 'Suv 1.5L', 'description': 'Ichimlik suvi'},
            'ru': {'name': 'Вода 1.5л', 'description': 'Питьевая вода'},
            'en': {'name': 'Water 1.5L', 'description': 'Drinking water'},
        },
        'product_unit': ProductUnit.ML.value,
        'unit_amount': Decimal('1500'),
        'price': Decimal('5000'),
        'quantity': 300,
        'shelf_location': 'D-02',
    },
    {
        'translations': {
            'uz': {'name': 'Tuxum 10 dona', 'description': 'Kategoriya C tuxum'},
            'ru': {'name': 'Яйца 10 шт', 'description': 'Яйца категория C'},
            'en': {'name': 'Eggs 10 pcs', 'description': 'Grade C eggs'},
        },
        'product_unit': ProductUnit.PIECE.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('18000'),
        'quantity': 80,
        'shelf_location': 'E-01',
    },
    {
        'translations': {
            'uz': {'name': 'Non lavash', 'description': 'Kunlik non'},
            'ru': {'name': 'Лаваш', 'description': 'Свежий лаваш'},
            'en': {'name': 'Lavash bread', 'description': 'Fresh lavash'},
        },
        'product_unit': ProductUnit.PIECE.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('6000'),
        'quantity': 150,
        'shelf_location': 'E-02',
    },
    {
        'translations': {
            'uz': {'name': 'Guruch', 'description': 'Oq guruch'},
            'ru': {'name': 'Рис', 'description': 'Белый рис'},
            'en': {'name': 'Rice', 'description': 'White rice'},
        },
        'product_unit': ProductUnit.KG.value,
        'unit_amount': Decimal('1'),
        'price': Decimal('16000'),
        'quantity': 400,
        'shelf_location': 'A-03',
    },
    {
        'translations': {
            'uz': {'name': 'Asal 250g', 'description': 'Tabiiy asal'},
            'ru': {'name': 'Мёд 250г', 'description': 'Натуральный мёд'},
            'en': {'name': 'Honey 250g', 'description': 'Natural honey'},
        },
        'product_unit': ProductUnit.GRAM.value,
        'unit_amount': Decimal('250'),
        'price': Decimal('45000'),
        'quantity': 50,
        'shelf_location': 'F-01',
    },
    {
        'translations': {
            'uz': {'name': 'Yogurt 400g', 'description': 'Qaymoqli yogurt'},
            'ru': {'name': 'Йогурт 400г', 'description': 'Йогурт'},
            'en': {'name': 'Yogurt 400g', 'description': 'Creamy yogurt'},
        },
        'product_unit': ProductUnit.GRAM.value,
        'unit_amount': Decimal('400'),
        'price': Decimal('11000'),
        'quantity': 90,
        'shelf_location': 'C-02',
    },
]


class Command(BaseCommand):
    help = "Mavjud mahsulotlarni tozalash va demo oziq-ovqat mahsulotlari qo'shish"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Barcha mahsulotlarni (va bog li qatorlarni) o\'chirish',
        )
        parser.add_argument(
            '--no-clear',
            action='store_true',
            help='Eskilarni o\'chirmasdan faqat yangi qo\'shish',
        )

    def handle(self, *args, **options):
        do_clear = options['clear'] or not options['no_clear']

        with transaction.atomic():
            if do_clear:
                deleted = self._clear_products()
                self.stdout.write(self.style.WARNING(f'O\'chirildi: {deleted} ta mahsulot'))

            category = self._get_or_create_grocery_category()
            created = 0
            for item in FAKE_PRODUCTS:
                data = dict(item)
                translations = data.pop('translations')
                ProductService.create_product(
                    translations=translations,
                    category=category,
                    price=data.pop('price'),
                    product_unit=data.pop('product_unit'),
                    unit_amount=data.pop('unit_amount'),
                    quantity=data.pop('quantity'),
                    shelf_location=data.pop('shelf_location', None),
                    is_active=True,
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Tayyor: {created} ta demo mahsulot (kategoriya id={category.pk}).'
        ))

    def _clear_products(self) -> int:
        from apps.inventory.models import StockReceiptItem
        from apps.orders.models import OrderProduct

        OrderProduct.objects.all().delete()
        StockReceiptItem.objects.all().delete()
        ProductSavedUser.objects.all().delete()
        ProductImage.objects.all().delete()
        ProductBarcode.objects.all().delete()

        qs = Products.all_objects.all()
        count = qs.count()
        for product in qs.iterator():
            product.delete(hard_delete=True)
        return count

    def _get_or_create_grocery_category(self) -> Category:
        existing = Category.objects.filter(
            translations__name__in=['Oziq-ovqat', 'Продукты', 'Groceries'],
        ).first()
        if existing:
            return existing

        cat = Category.objects.create(
            parent=None,
            order=FAKE_GROCERY_CATEGORY['order'],
            is_active=FAKE_GROCERY_CATEGORY['is_active'],
        )
        for lang, trans in FAKE_GROCERY_CATEGORY['translations'].items():
            cat.set_current_language(lang)
            cat.name = trans['name']
            cat.save()
        return cat
