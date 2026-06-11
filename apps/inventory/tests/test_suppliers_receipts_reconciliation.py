from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.models import Products
from apps.categories.models import Category
from apps.inventory.models import (
    Supplier,
    StockReceipt,
    StockReceiptItem,
    ReceiptStatus,
    SupplierReconciliationAct,
    ReconciliationActStatus,
)
from apps.inventory.services.receipt import post_stock_receipt, cancel_stock_receipt

User = get_user_model()


class InventoryApiTests(TestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='Admin')
        self.user = User.objects.create_user(phone='+998901234567', password='pass')
        self.user.groups.add(self.admin_group)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.supplier = Supplier.objects.create(name='ООО Поставщик', inn='123456789')
        self.category = Category.objects.create(is_active=True, is_deleted=False)
        self.product = Products.objects.create(
            category=self.category,
            price=Decimal('10000'),
            quantity=5,
            is_active=True,
            is_deleted=False,
        )
        self.product.set_current_language('ru')
        self.product.name = 'Молоко'
        self.product.save()

    def _create_draft_receipt_with_item(self):
        receipt = StockReceipt.objects.create(
            supplier=self.supplier,
            doc_number='P-001',
            doc_date='2026-06-01',
            created_by=self.user,
        )
        StockReceiptItem.objects.create(
            receipt=receipt,
            product=self.product,
            quantity=10,
            purchase_price=Decimal('8000'),
            sell_price=Decimal('10000'),
            line_total=Decimal('80000'),
            product_name_snapshot='Молоко',
        )
        receipt.subtotal = Decimal('80000')
        receipt.save(update_fields=['subtotal'])
        return receipt

    def test_supplier_crud(self):
        resp = self.client.post('/api/v1/inventory/suppliers/', {
            'name': 'Новый поставщик',
            'phone': '+998901112233',
            'inn': '998877',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        pk = resp.data['id']
        resp = self.client.get(f'/api/v1/inventory/suppliers/{pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'Новый поставщик')

    def test_receipt_post_increases_stock(self):
        receipt = self._create_draft_receipt_with_item()
        post_stock_receipt(receipt, posted_by=self.user)
        receipt.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 15)
        self.assertEqual(receipt.status, ReceiptStatus.POSTED)

    def test_receipt_cancel_reverses_stock(self):
        receipt = self._create_draft_receipt_with_item()
        post_stock_receipt(receipt, posted_by=self.user)
        cancel_stock_receipt(receipt, cancelled_by=self.user)
        receipt.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)
        self.assertEqual(receipt.status, ReceiptStatus.CANCELLED)

    def test_supplier_statement_posted_only(self):
        receipt = self._create_draft_receipt_with_item()
        post_stock_receipt(receipt, posted_by=self.user)
        resp = self.client.get(
            f'/api/v1/inventory/suppliers/{self.supplier.pk}/statement/',
            {'date_from': '2026-06-01', 'date_to': '2026-06-30', 'opening_balance': '1000'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_receipts'], 1)
        self.assertEqual(resp.data['total_amount'], '80000.00')
        self.assertEqual(resp.data['closing_balance'], '81000.00')

    def test_reconciliation_act_confirm(self):
        receipt = self._create_draft_receipt_with_item()
        post_stock_receipt(receipt, posted_by=self.user)
        resp = self.client.post('/api/v1/inventory/reconciliation-acts/', {
            'supplier_id': self.supplier.pk,
            'period_from': '2026-06-01',
            'period_to': '2026-06-30',
            'opening_balance': '5000',
            'notes': 'Июнь',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        act_id = resp.data['id']
        resp = self.client.post(f'/api/v1/inventory/reconciliation-acts/{act_id}/confirm/')
        self.assertEqual(resp.status_code, 200)
        act = SupplierReconciliationAct.objects.get(pk=act_id)
        self.assertEqual(act.status, ReconciliationActStatus.CONFIRMED)
        self.assertEqual(act.receipts_total, Decimal('80000.00'))
        self.assertEqual(act.closing_balance, Decimal('85000.00'))
