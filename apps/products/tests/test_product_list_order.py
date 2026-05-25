from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.categories.models import Category
from apps.products.models import Products
from apps.products.services import ProductService


class ProductListOrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(is_active=True, order=0)
        self.category.set_current_language('uz')
        self.category.name = 'Test'
        self.category.save()

    def _create_product(self, name: str) -> Products:
        return ProductService.create_product(
            translations={'uz': {'name': name}},
            category=self.category,
            price=Decimal('1000'),
            quantity=1,
        )

    def test_list_newest_first_by_id(self):
        first = self._create_product('First')
        second = self._create_product('Second')
        third = self._create_product('Third')

        response = self.client.get('/api/v1/products/')
        self.assertEqual(response.status_code, 200)

        if isinstance(response.data, dict) and 'results' in response.data:
            ids = [item['id'] for item in response.data['results']]
        else:
            ids = [item['id'] for item in response.data]

        self.assertGreater(third.pk, second.pk)
        self.assertGreater(second.pk, first.pk)
        self.assertEqual(ids[:3], [third.pk, second.pk, first.pk])
