from decimal import Decimal
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.products.unit_pricing import (
    UnitPricingError,
    compute_line_pricing,
    convert_quantity,
)


class UnitPricingTests(SimpleTestCase):
    def _product(self, **kwargs):
        defaults = {
            'pk': 1,
            'product_unit': 'kg',
            'unit_amount': Decimal('1'),
            'price': Decimal('20000'),
            'price_discount': None,
            'is_discount': False,
            'sale_unit': 'weight',
        }
        defaults.update(kwargs)
        p = Mock()
        for k, v in defaults.items():
            setattr(p, k, v)
        p.current_price = kwargs.get('current_price', defaults['price'])
        return p

    def test_kg_fractional_total(self):
        p = self._product(product_unit='kg', price=Decimal('20000'))
        line = compute_line_pricing(p, Decimal('1.5'))
        self.assertEqual(line['total_price'], Decimal('30000.00'))
        self.assertEqual(line['normalized_quantity'], Decimal('1.500'))

    def test_gram_to_kg_conversion(self):
        p = self._product(product_unit='kg', price=Decimal('10000'))
        line = compute_line_pricing(p, Decimal('500'), product_unit='gram')
        self.assertEqual(line['normalized_quantity'], Decimal('0.500'))
        self.assertEqual(line['total_price'], Decimal('5000.00'))

    def test_ml_liter_conversion(self):
        p = self._product(product_unit='liter', price=Decimal('12000'))
        line = compute_line_pricing(p, Decimal('500'), product_unit='ml')
        self.assertEqual(line['normalized_quantity'], Decimal('0.500'))
        self.assertEqual(line['total_price'], Decimal('6000.00'))

    def test_piece_times_three(self):
        p = self._product(product_unit='piece', price=Decimal('10000'), sale_unit='piece')
        line = compute_line_pricing(p, Decimal('3'))
        self.assertEqual(line['total_price'], Decimal('30000.00'))

    def test_cola_500ml_pack(self):
        p = self._product(
            product_unit='ml',
            unit_amount=Decimal('500'),
            price=Decimal('8000'),
            sale_unit='piece',
        )
        line = compute_line_pricing(p, Decimal('500'))
        self.assertEqual(line['total_price'], Decimal('8000.00'))
        line2 = compute_line_pricing(p, Decimal('1000'))
        self.assertEqual(line2['total_price'], Decimal('16000.00'))

    def test_piece_to_ml_bottles(self):
        p = self._product(
            product_unit='ml',
            unit_amount=Decimal('500'),
            price=Decimal('8000'),
            sale_unit='piece',
        )
        line = compute_line_pricing(p, Decimal('2'), product_unit='piece')
        self.assertEqual(line['normalized_quantity'], Decimal('1000.000'))
        self.assertEqual(line['total_price'], Decimal('16000.00'))

    def test_piece_to_gram_pack(self):
        p = self._product(
            product_unit='gram',
            unit_amount=Decimal('400'),
            price=Decimal('11000'),
            sale_unit='piece',
        )
        line = compute_line_pricing(p, Decimal('1'), product_unit='piece')
        self.assertEqual(line['normalized_quantity'], Decimal('400.000'))
        self.assertEqual(line['total_price'], Decimal('11000.00'))

    def test_incompatible_units(self):
        p = self._product(product_unit='kg')
        with self.assertRaises(UnitPricingError):
            convert_quantity(Decimal('1'), 'liter', 'kg')
