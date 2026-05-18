"""
ProductUnit: choices, Swagger docs, and per-unit field guide.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from apps.core.enums import ProductUnit


@dataclass(frozen=True)
class ProductUnitSpec:
    value: str
    label: str
    label_uz: str
    family: str
    unit_amount_default: str
    unit_amount_hint: str
    price_hint: str
    stock_quantity_hint: str
    order_quantity_hint: str
    cart_units_allowed: Tuple[str, ...]
    example: str

    def to_api_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['cart_units_allowed'] = list(self.cart_units_allowed)
        return d


PRODUCT_UNIT_SPECS: Dict[str, ProductUnitSpec] = {
    ProductUnit.PIECE.value: ProductUnitSpec(
        value=ProductUnit.PIECE.value,
        label='Штука (dona)',
        label_uz='Dona',
        family='piece',
        unit_amount_default='1',
        unit_amount_hint='Har doim `1` (bitta dona uchun narx).',
        price_hint='`price` = 1 dona narxi (UZS).',
        stock_quantity_hint='`quantity` = nechta dona skladda (butun son).',
        order_quantity_hint='Savat: `quantity` butun son (1, 2, 3). Kasr yo‘q.',
        cart_units_allowed=(ProductUnit.PIECE.value,),
        example='Tuxum, non, paket — product_unit=piece, unit_amount=1, price=5000',
    ),
    ProductUnit.KG.value: ProductUnitSpec(
        value=ProductUnit.KG.value,
        label='Килограмм (kg)',
        label_uz='Kilogramm',
        family='weight',
        unit_amount_default='1',
        unit_amount_hint='Odatda `1` — narx 1 kg uchun.',
        price_hint='`price` = 1 kg narxi (UZS).',
        stock_quantity_hint='`quantity` = kg miqdori skladda (butun yoki kasr).',
        order_quantity_hint='Savat: `quantity` kasr mumkin (1.5). `product_unit`: kg yoki gram.',
        cart_units_allowed=(ProductUnit.KG.value, ProductUnit.GRAM.value, ProductUnit.PIECE.value),
        example='Kartoshka — product_unit=kg, unit_amount=1, price=20000',
    ),
    ProductUnit.GRAM.value: ProductUnitSpec(
        value=ProductUnit.GRAM.value,
        label='Грамм (g)',
        label_uz='Gramm',
        family='weight',
        unit_amount_default='1',
        unit_amount_hint='Kam uchraydi; odatda kg ishlating. Agar gram bo‘lsa — narx 1 g uchun.',
        price_hint='`price` = 1 g narxi (kam ishlatiladi; kg qulayroq).',
        stock_quantity_hint='Sklad odatda kg da saqlanadi; catalog_unit=gram bo‘lsa quantity gramda.',
        order_quantity_hint='Savat: gram yoki kg (avto konvert).',
        cart_units_allowed=(ProductUnit.GRAM.value, ProductUnit.KG.value, ProductUnit.PIECE.value),
        example='Mayda og‘irlik — product_unit=gram, unit_amount=1',
    ),
    ProductUnit.LITER.value: ProductUnitSpec(
        value=ProductUnit.LITER.value,
        label='Литр (l)',
        label_uz='Litr',
        family='volume',
        unit_amount_default='1',
        unit_amount_hint='Odatda `1` — narx 1 litr uchun.',
        price_hint='`price` = 1 L narxi (UZS).',
        stock_quantity_hint='`quantity` = litr (suv, moy oqimida).',
        order_quantity_hint='Savat: `quantity` kasr (0.5). `product_unit`: liter yoki ml.',
        cart_units_allowed=(ProductUnit.LITER.value, ProductUnit.ML.value, ProductUnit.PIECE.value),
        example='Suv oqim — product_unit=liter, unit_amount=1, price=10000',
    ),
    ProductUnit.ML.value: ProductUnitSpec(
        value=ProductUnit.ML.value,
        label='Миллилитр (ml)',
        label_uz='Millilitr',
        family='volume',
        unit_amount_default='500',
        unit_amount_hint='Butilka uchun: `500`, `1000` va hokazo (bitta shisha hajmi).',
        price_hint='`price` = `unit_amount` ml uchun narx (masalan 8000 / 500ml).',
        stock_quantity_hint='`quantity` = butilka soni (agar unit_amount=500 bo‘lsa).',
        order_quantity_hint='Savat: ml, liter yoki piece (2 dona = 2×unit_amount).',
        cart_units_allowed=(ProductUnit.ML.value, ProductUnit.LITER.value, ProductUnit.PIECE.value),
        example='Cola 0.5L — product_unit=ml, unit_amount=500, price=8000',
    ),
}


def get_product_unit_spec(unit: str) -> ProductUnitSpec:
    key = (unit or ProductUnit.PIECE.value).strip().lower()
    if key not in PRODUCT_UNIT_SPECS:
        raise ValueError(f'Unknown product_unit: {unit!r}')
    return PRODUCT_UNIT_SPECS[key]


def product_unit_choices() -> List[Tuple[str, str]]:
    """Django / DRF dropdown: (value, label)."""
    return [(s.value, f'{s.value} — {s.label}') for s in PRODUCT_UNIT_SPECS.values()]


def product_unit_choices_payload() -> List[Dict[str, Any]]:
    """GET /products/unit-options/ — mobile/admin form builder."""
    return [s.to_api_dict() for s in PRODUCT_UNIT_SPECS.values()]


def product_unit_openapi_description() -> str:
    lines = [
        '**`product_unit`** — mahsulot qanday sotiladi. Har bir qiymat uchun mos maydonlar:',
        '',
    ]
    for spec in PRODUCT_UNIT_SPECS.values():
        lines.append(f'### `{spec.value}` — {spec.label}')
        lines.append(f'- **unit_amount:** {spec.unit_amount_hint} (default: `{spec.unit_amount_default}`)')
        lines.append(f'- **price:** {spec.price_hint}')
        lines.append(f'- **quantity (sklad):** {spec.stock_quantity_hint}')
        lines.append(f'- **savat (order):** {spec.order_quantity_hint}')
        lines.append(f'- **Savatda ruxsat:** `{", ".join(spec.cart_units_allowed)}`')
        lines.append(f'- **Misol:** {spec.example}')
        lines.append('')
    return '\n'.join(lines)


def unit_amount_help_for(product_unit: str) -> str:
    return get_product_unit_spec(product_unit).unit_amount_hint
