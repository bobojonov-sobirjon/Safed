"""Reusable DRF fields for products."""
from decimal import Decimal

from rest_framework import serializers

from apps.products.product_unit_specs import product_unit_choices, unit_amount_help_for


class ProductUnitChoiceField(serializers.ChoiceField):
    """ChoiceField with unified product_unit labels and OpenAPI enum."""

    def __init__(self, **kwargs):
        kwargs.setdefault('choices', product_unit_choices())
        kwargs.setdefault(
            'help_text',
            'piece | kg | gram | liter | ml. Batafsil: GET /products/unit-options/',
        )
        super().__init__(**kwargs)


class ProductUnitAmountField(serializers.DecimalField):
    """unit_amount — meaning depends on product_unit (see unit-options)."""

    def __init__(self, **kwargs):
        kwargs.setdefault('max_digits', 12)
        kwargs.setdefault('decimal_places', 3)
        kwargs.setdefault('min_value', Decimal('0.001'))
        kwargs.setdefault('default', Decimal('1'))
        kwargs.setdefault(
            'help_text',
            'Narx qaysi hajm uchun. piece→1; kg/liter→1; ml butilka→500. '
            'GET /products/unit-options/',
        )
        super().__init__(**kwargs)

    def bind(self, field_name, parent):
        super().bind(field_name, parent)
        if parent and hasattr(parent, 'initial_data') and isinstance(parent.initial_data, dict):
            pu = parent.initial_data.get('product_unit')
            if pu:
                self.help_text = unit_amount_help_for(str(pu).lower())
