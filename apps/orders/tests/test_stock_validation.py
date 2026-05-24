from decimal import Decimal
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.core.enums import ProductUnit
from apps.orders.services.stock_validation import (
    INSUFFICIENT_STOCK_DETAIL,
    build_stock_shortage_message,
    collect_insufficient_stock,
)


class StockValidationTests(SimpleTestCase):
    def _product(self, **kwargs):
        p = Mock()
        p.id = kwargs.get('id', 1)
        p.quantity = kwargs.get('quantity', 5)
        p.product_unit = kwargs.get('product_unit', ProductUnit.PIECE.value)
        p.unit_amount = kwargs.get('unit_amount', Decimal('1'))
        return p

    def test_piece_shortage_message_uzbek(self):
        product = self._product(quantity=5)
        msg = build_stock_shortage_message(product, available=5, requested=10)
        self.assertIn('Omborda faqat 5 dona bor', msg)
        self.assertIn("10 dona so'radingiz", msg)

    def test_collect_insufficient_stock_piece(self):
        product = self._product(quantity=5)
        items = [{
            'product_id': 1,
            'normalized_quantity': Decimal('10'),
        }]
        result = collect_insufficient_stock({1: product}, items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['available_quantity'], 5)
        self.assertEqual(result[0]['requested_quantity'], '10')
        self.assertIn('Omborda faqat 5 dona bor', result[0]['message'])

    def test_collect_skips_when_enough_stock(self):
        product = self._product(quantity=20)
        items = [{
            'product_id': 1,
            'normalized_quantity': Decimal('10'),
        }]
        self.assertEqual(collect_insufficient_stock({1: product}, items), [])

    def test_detail_constant_uzbek(self):
        self.assertIn('yetarli emas', INSUFFICIENT_STOCK_DETAIL.lower())
