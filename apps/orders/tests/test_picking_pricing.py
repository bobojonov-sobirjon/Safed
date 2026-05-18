from decimal import Decimal
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.core.enums import ProductUnit
from apps.orders.services.picking import default_picking_input_unit
from apps.products.unit_pricing import line_total_from_normalized


class PickingPricingTests(SimpleTestCase):
    def _product(self, **kwargs):
        p = Mock()
        p.pk = 28
        p.product_unit = kwargs.get('product_unit', 'gram')
        p.unit_amount = kwargs.get('unit_amount', Decimal('400'))
        p.sale_unit = 'weight'
        return p

    def _line(self, **kwargs):
        line = Mock()
        line.product_unit = kwargs.get('product_unit', 'piece')
        line.quantity = kwargs.get('quantity', Decimal('2'))
        line.normalized_quantity = kwargs.get('normalized_quantity', Decimal('800'))
        line.ordered_quantity = kwargs.get('ordered_quantity', None)
        return line

    def test_default_unit_piece_for_pack_checkout(self):
        product = self._product(unit_amount=Decimal('400'))
        line = self._line(product_unit='piece', quantity=Decimal('2'), normalized_quantity=Decimal('800'))
        self.assertEqual(default_picking_input_unit(line, product), ProductUnit.PIECE.value)

    def test_piece_picking_total_yogurt_four_packs(self):
        unit_price = Decimal('11000')
        ua = Decimal('400')
        normalized = Decimal('4') * ua
        total = line_total_from_normalized(
            unit_price=unit_price,
            normalized_quantity=normalized,
            unit_amount=ua,
        )
        self.assertEqual(total, Decimal('44000.00'))

    def test_gram_picking_two_grams_is_tiny(self):
        unit_price = Decimal('45000')
        ua = Decimal('250')
        total = line_total_from_normalized(
            unit_price=unit_price,
            normalized_quantity=Decimal('2'),
            unit_amount=ua,
        )
        self.assertEqual(total, Decimal('360.00'))
