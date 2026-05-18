from decimal import Decimal
from django.test import SimpleTestCase

from apps.core.enums import ProductUnit
from apps.products.catalog_units import enrich_translations_grammage, format_size_label


class CatalogUnitsTests(SimpleTestCase):
    def test_format_kg(self):
        self.assertEqual(format_size_label(ProductUnit.KG.value, Decimal('1'), lang='ru'), '1 кг')

    def test_format_ml_pack(self):
        self.assertEqual(
            format_size_label(ProductUnit.ML.value, Decimal('500'), lang='uz'),
            '500 ml',
        )

    def test_enrich_grammage(self):
        trans = {'ru': {'name': 'Картофель'}}
        out = enrich_translations_grammage(trans, ProductUnit.KG.value, Decimal('1'))
        self.assertEqual(out['ru']['grammage'], '1 кг')
        self.assertEqual(out['ru']['name'], 'Картофель')
