"""Full purchase (закупка / приход) flow for admin panel."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.categories.models import Category
from apps.products.models import Products
from apps.inventory.models import ReceiptStatus, Supplier

User = get_user_model()


class PurchaseReceiptFlowTests(TestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        self.user = User.objects.create_user(phone='+998909998877', password='pass')
        self.user.groups.add(admin_group)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.supplier = Supplier.objects.create(name='Поставщик 1')
        self.category = Category.objects.create(is_active=True, is_deleted=False)
        self.cola = Products.objects.create(
            category=self.category, price=Decimal('8000'), quantity=0, is_active=True, is_deleted=False,
        )
        self.cola.set_current_language('ru')
        self.cola.name = 'COCA-COLA'
        self.cola.save()
        self.fanta = Products.objects.create(
            category=self.category, price=Decimal('5000'), quantity=0, is_active=True, is_deleted=False,
        )
        self.fanta.set_current_language('ru')
        self.fanta.name = 'Fanta'
        self.fanta.save()

    def test_full_purchase_ui_flow(self):
        # 1) Create document (top Create)
        resp = self.client.post('/api/v1/inventory/receipts/', {
            'supplier_id': self.supplier.pk,
            'notes': 'Оптовая закупка',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        receipt_id = resp.data['id']
        self.assertEqual(resp.data['status'], 'draft')
        self.assertEqual(resp.data['doc_number'], '1')
        self.assertEqual(resp.data['subtotal'], '0.00')

        # 2) Add items (bottom Create)
        resp = self.client.post(f'/api/v1/inventory/receipts/{receipt_id}/items/', {
            'product_id': self.cola.pk,
            'quantity': 10,
            'purchase_price': '15000',
            'sell_price': '18000',
            'update_catalog_price': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['line_total'], '150000.00')

        resp = self.client.post(f'/api/v1/inventory/receipts/{receipt_id}/items/', {
            'product_id': self.fanta.pk,
            'quantity': 2,
            'purchase_price': '5000',
            'margin_percent': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['line_total'], '10000.00')

        # 3) Detail shows total sum
        resp = self.client.get(f'/api/v1/inventory/receipts/{receipt_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['subtotal'], '160000.00')
        self.assertEqual(resp.data['debt'], '160000.00')
        self.assertEqual(resp.data['payment_status'], 'unpaid')
        self.assertEqual(resp.data['items_count'], 2)
        self.assertEqual(resp.data['total_quantity'], 12)

        # 4) Post → stock increases
        resp = self.client.post(f'/api/v1/inventory/receipts/{receipt_id}/post/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'posted')
        self.cola.refresh_from_db()
        self.fanta.refresh_from_db()
        self.assertEqual(self.cola.quantity, 10)
        self.assertEqual(self.fanta.quantity, 2)
        self.assertEqual(self.cola.price, Decimal('18000.00'))  # update_catalog_price

        # 5) Payment
        resp = self.client.post(f'/api/v1/inventory/receipts/{receipt_id}/payment/', {
            'paid_amount': '50000',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['paid_amount'], '50000.00')
        self.assertEqual(resp.data['debt'], '110000.00')
        self.assertEqual(resp.data['payment_status'], 'partial')

        # 6) Unpost reverses stock
        resp = self.client.post(f'/api/v1/inventory/receipts/{receipt_id}/unpost/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'draft')
        self.cola.refresh_from_db()
        self.fanta.refresh_from_db()
        self.assertEqual(self.cola.quantity, 0)
        self.assertEqual(self.fanta.quantity, 0)

    def test_list_filters(self):
        self.client.post('/api/v1/inventory/receipts/', {'supplier_id': self.supplier.pk}, format='json')
        resp = self.client.get('/api/v1/inventory/receipts/', {'status': 'draft', 'q': 'Поставщик'})
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertGreaterEqual(len(rows), 1)
