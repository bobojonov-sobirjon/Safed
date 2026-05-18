"""
Product unit conversion and order-line pricing (Decimal only).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Any, Dict, Optional, TYPE_CHECKING

from apps.core.enums import ProductUnit

if TYPE_CHECKING:
    from apps.products.models import Products

_TWO = Decimal('0.01')
_THREE = Decimal('0.001')


class UnitPricingError(ValueError):
    def __init__(self, message: str, *, code: str = 'invalid_unit'):
        self.message = message
        self.code = code
        super().__init__(message)


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _unit(value: str) -> ProductUnit:
    try:
        return ProductUnit(value)
    except ValueError as exc:
        raise UnitPricingError(
            f'Недопустимая единица: {value!r}. Допустимо: piece, kg, gram, liter, ml.',
            code='unknown_unit',
        ) from exc


def unit_family(unit: str) -> str:
    return _unit(unit).family()


def units_compatible(from_unit: str, to_unit: str) -> bool:
    return unit_family(from_unit) == unit_family(to_unit)


def _to_kg(quantity: Decimal, unit: ProductUnit) -> Decimal:
    if unit == ProductUnit.KG:
        return quantity
    if unit == ProductUnit.GRAM:
        return quantity / Decimal('1000')
    raise UnitPricingError('Ожидалась единица веса (kg / gram).', code='incompatible_unit')


def _from_kg(kg: Decimal, unit: ProductUnit) -> Decimal:
    if unit == ProductUnit.KG:
        return kg
    if unit == ProductUnit.GRAM:
        return kg * Decimal('1000')
    raise UnitPricingError('Ожидалась единица веса (kg / gram).', code='incompatible_unit')


def _to_liter(quantity: Decimal, unit: ProductUnit) -> Decimal:
    if unit == ProductUnit.LITER:
        return quantity
    if unit == ProductUnit.ML:
        return quantity / Decimal('1000')
    raise UnitPricingError('Ожидалась единица объёма (liter / ml).', code='incompatible_unit')


def _from_liter(liters: Decimal, unit: ProductUnit) -> Decimal:
    if unit == ProductUnit.LITER:
        return liters
    if unit == ProductUnit.ML:
        return liters * Decimal('1000')
    raise UnitPricingError('Ожидалась единица объёма (liter / ml).', code='incompatible_unit')


def convert_quantity(
    quantity: Decimal,
    from_unit: str,
    to_unit: str,
    *,
    unit_amount: Decimal = Decimal('1'),
) -> Decimal:
    """
    Convert quantity between compatible units.
    piece → ml/liter: quantity × unit_amount (one piece = one priced pack).
    """
    qty = _d(quantity)
    if qty <= 0:
        raise UnitPricingError('Количество должно быть больше 0.', code='quantity')

    src = _unit(from_unit)
    dst = _unit(to_unit)
    if src == dst:
        return qty.quantize(_THREE)

    if src == ProductUnit.PIECE and dst != ProductUnit.PIECE:
        ua = _d(unit_amount)
        if ua <= 0:
            raise UnitPricingError('unit_amount должен быть > 0.', code='unit_amount')
        # 1 dona = bitta qadoq: unit_amount shu birlikda (400 g, 500 ml, 1 kg, …)
        return (qty * ua).quantize(_THREE)

    if dst == ProductUnit.PIECE and src != ProductUnit.PIECE:
        raise UnitPricingError(
            f'Нельзя конвертировать {from_unit} в piece. '
            f'Укажите product_unit=piece и quantity в штуках.',
            code='incompatible_unit',
        )

    if src.family() == 'weight' and dst.family() == 'weight':
        kg = _to_kg(qty, src)
        return _from_kg(kg, dst).quantize(_THREE)

    if src.family() == 'volume' and dst.family() == 'volume':
        liters = _to_liter(qty, src)
        return _from_liter(liters, dst).quantize(_THREE)

    raise UnitPricingError(
        f'Несовместимые единицы: {from_unit} и {to_unit}.',
        code='incompatible_unit',
    )


def catalog_unit_for_product(product: 'Products') -> str:
    unit = getattr(product, 'product_unit', None) or ProductUnit.PIECE.value
    if unit:
        return unit
    from apps.core.enums import SaleUnit

    if getattr(product, 'sale_unit', None) == SaleUnit.WEIGHT.value:
        return ProductUnit.KG.value
    return ProductUnit.PIECE.value


def unit_amount_for_product(product: 'Products') -> Decimal:
    ua = _d(getattr(product, 'unit_amount', None) or 1)
    return ua if ua > 0 else Decimal('1')


def is_fractional_unit(unit: str) -> bool:
    return unit in ProductUnit.fractional_units()


def validate_quantity_for_unit(quantity: Decimal, unit: str, *, product_id: Optional[int] = None) -> Decimal:
    qty = _d(quantity).quantize(_THREE)
    if qty <= 0:
        raise UnitPricingError('Количество должно быть больше 0.', code='quantity')
    if not is_fractional_unit(unit):
        if (qty % Decimal('1')) != Decimal('0'):
            label = f'Продукт {product_id}: ' if product_id else ''
            raise UnitPricingError(
                f'{label}для единицы piece укажите целое количество.',
                code='quantity',
            )
        if qty < 1:
            raise UnitPricingError(
                f'Продукт {product_id}: минимум 1 шт.' if product_id else 'Минимум 1 шт.',
                code='quantity',
            )
    return qty


def compute_line_pricing(
    product: 'Products',
    quantity: Decimal,
    *,
    product_unit: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns quantity, product_unit, normalized_quantity, unit_price, total_price.
    Price applies per unit_amount in catalog product_unit.
    """
    catalog_unit = catalog_unit_for_product(product)
    ua = unit_amount_for_product(product)
    request_unit = product_unit or catalog_unit

    qty = validate_quantity_for_unit(quantity, request_unit, product_id=product.pk)
    normalized = convert_quantity(qty, request_unit, catalog_unit, unit_amount=ua)
    unit_price = _d(product.current_price).quantize(_TWO)
    effective = (normalized / ua).quantize(_THREE)
    total_price = (effective * unit_price).quantize(_TWO)

    return {
        'quantity': qty,
        'product_unit': request_unit,
        'normalized_quantity': normalized,
        'unit_price': unit_price,
        'total_price': total_price,
        'catalog_unit': catalog_unit,
        'unit_amount': ua,
    }


def line_total_from_normalized(
    *,
    unit_price: Decimal,
    normalized_quantity: Decimal,
    unit_amount: Decimal,
) -> Decimal:
    ua = _d(unit_amount)
    if ua <= 0:
        ua = Decimal('1')
    effective = (_d(normalized_quantity) / ua).quantize(_THREE)
    return (effective * _d(unit_price)).quantize(_TWO)


def stock_units_required(product: 'Products', normalized_quantity: Decimal) -> Decimal:
    """
    Amount to compare with product.quantity (warehouse).
    - piece: pieces
    - kg / liter: normalized amount in catalog unit
    - ml with unit_amount > 1: packages (bottles) = normalized_ml / unit_amount
    """
    catalog = catalog_unit_for_product(product)
    ua = unit_amount_for_product(product)
    norm = _d(normalized_quantity)

    if catalog == ProductUnit.PIECE.value:
        return norm.quantize(_THREE)

    if catalog in (ProductUnit.ML.value, ProductUnit.GRAM.value) and ua > Decimal('1'):
        return (norm / ua).quantize(_THREE, rounding=ROUND_CEILING)

    return norm.quantize(_THREE)


def product_applies_weight_buffer(product: 'Products') -> bool:
    return catalog_unit_for_product(product) in ProductUnit.weight_units()
