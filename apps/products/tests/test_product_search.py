from django.test import TestCase

from apps.categories.models import Category
from apps.products.models import Products
from apps.products.services.product_search import filter_products_by_query


class ProductMultilingualSearchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(is_active=True, is_deleted=False)
        self.category.set_current_language('uz')
        self.category.name = 'Oziq-ovqat'
        self.category.save()

        self.product = Products.objects.create(
            category=self.category,
            price=10000,
            is_active=True,
            is_deleted=False,
        )
        self.product.set_current_language('uz')
        self.product.name = 'Olma'
        self.product.save()
        self.product.set_current_language('ru')
        self.product.name = 'Яблоко'
        self.product.save()

    def test_search_matches_russian_while_default_language_uz(self):
        qs = Products.objects.filter(is_active=True)
        found = filter_products_by_query(qs, 'Яблоко')
        self.assertEqual(list(found.values_list('pk', flat=True)), [self.product.pk])

    def test_search_matches_uzbek_name(self):
        qs = Products.objects.filter(is_active=True)
        found = filter_products_by_query(qs, 'Olma')
        self.assertEqual(list(found.values_list('pk', flat=True)), [self.product.pk])
