from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.categories.models import Category
from apps.core.enums import ProductUnit, UserGroup
from apps.inventory.services.stock import adjust_product_stock, restock_product_by_barcode
from apps.products.models import ProductBarcode, Products
from apps.realtime.models import Notification


def _make_product(*, quantity: int = 10, barcode: str = '4600000000012') -> Products:
    category = Category.objects.create(is_active=True)
    category.set_current_language('ru')
    category.name = 'Тест'
    category.save()
    product = Products.objects.create(
        category=category,
        product_unit=ProductUnit.PIECE.value,
        unit_amount=Decimal('1'),
        price=Decimal('1000'),
        quantity=quantity,
    )
    product.set_current_language('ru')
    product.name = 'Молоко'
    product.save()
    ProductBarcode.objects.create(product=product, barcode=barcode)
    return product


class ProductRestockApiTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name=UserGroup.OPERATOR.value)
        Group.objects.get_or_create(name=UserGroup.SUPER_ADMIN.value)
        Group.objects.get_or_create(name=UserGroup.ADMIN.value)

        self.operator = CustomUser.objects.create_user(phone='998901111111', password='pass')
        self.operator.groups.add(Group.objects.get(name=UserGroup.OPERATOR.value))
        self.admin = CustomUser.objects.create_user(phone='998902222222', password='pass')
        self.admin.groups.add(Group.objects.get(name=UserGroup.ADMIN.value))

        self.product = _make_product(quantity=20)
        self.client = APIClient()
        self.url = '/api/v1/inventory/products/restock/'

    def test_operator_restock_adds_quantity(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post(
            self.url,
            {'barcode': '4600000000012', 'quantity': 15},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 35)
        self.assertEqual(response.data['added_quantity'], 15)

    def test_admin_forbidden(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.url,
            {'barcode': '4600000000012', 'quantity': 5},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_barcode_404(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post(
            self.url,
            {'barcode': 'missing', 'quantity': 5},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(LOW_STOCK_THRESHOLD=5)
class LowStockNotificationTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name=UserGroup.OPERATOR.value)
        Group.objects.get_or_create(name=UserGroup.SUPER_ADMIN.value)
        self.operator = CustomUser.objects.create_user(phone='998903333333', password='pass')
        self.operator.groups.add(Group.objects.get(name=UserGroup.OPERATOR.value))
        self.product = _make_product(quantity=6, barcode='4600000000099')

    @patch('apps.realtime.services.notify._push_ws')
    def test_notify_when_crossing_threshold(self, _ws):
        adjust_product_stock(self.product.pk, -2)
        self.assertEqual(
            Notification.objects.filter(user=self.operator, type='staff_low_stock').count(),
            1,
        )
        n = Notification.objects.get(user=self.operator, type='staff_low_stock')
        self.assertIn('заканчивается', n.body.lower())
        self.assertIn('молоко', n.body.lower())

    @patch('apps.realtime.services.notify._push_ws')
    def test_no_repeat_while_already_low(self, _ws):
        adjust_product_stock(self.product.pk, -2)
        adjust_product_stock(self.product.pk, -1)
        self.assertEqual(
            Notification.objects.filter(user=self.operator, type='staff_low_stock').count(),
            1,
        )

    @patch('apps.realtime.services.notify._push_ws')
    def test_restock_service_increases_quantity(self, _ws):
        product = restock_product_by_barcode('4600000000099', 10)
        self.assertEqual(product.quantity, 16)
