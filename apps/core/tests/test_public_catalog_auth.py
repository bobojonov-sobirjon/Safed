"""Guest catalog access (App Store Guideline 5.1.1)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.categories.models import Category
from apps.news.models import Posts
from apps.products.models import Products
from apps.products.services import ProductService


class PublicCatalogAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(is_active=True, order=0)
        self.category.set_current_language('uz')
        self.category.name = 'Test'
        self.category.save()
        self.product = ProductService.create_product(
            translations={'uz': {'name': 'Mahsulot'}},
            category=self.category,
            price=Decimal('1000'),
            quantity=1,
        )
        self.post = Posts.objects.create(is_active=True)
        self.post.set_current_language('uz')
        self.post.title = 'Yangilik'
        self.post.save()

    def test_products_list_without_token(self):
        response = self.client.get('/api/v1/products/')
        self.assertEqual(response.status_code, 200)

    def test_products_list_with_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-valid-jwt')
        response = self.client.get('/api/v1/products/')
        self.assertEqual(response.status_code, 200)

    def test_product_detail_without_token(self):
        response = self.client.get(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_news_list_without_token(self):
        response = self.client.get('/api/v1/posts/')
        self.assertEqual(response.status_code, 200)

    def test_news_detail_without_token(self):
        response = self.client.get(f'/api/v1/posts/{self.post.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_categories_without_token(self):
        response = self.client.get('/api/v1/categories/')
        self.assertEqual(response.status_code, 200)
