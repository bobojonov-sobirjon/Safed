"""
Display labels for product size (grammage) and translation helpers.
Pricing math lives in unit_pricing.py.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from apps.core.enums import ProductUnit, Language

_THREE = Decimal('0.001')

_UNIT_SHORT: Dict[str, Dict[str, str]] = {
    'ru': {
        ProductUnit.PIECE.value: 'шт',
        ProductUnit.KG.value: 'кг',
        ProductUnit.GRAM.value: 'г',
        ProductUnit.LITER.value: 'л',
        ProductUnit.ML.value: 'мл',
    },
    'uz': {
        ProductUnit.PIECE.value: 'dona',
        ProductUnit.KG.value: 'kg',
        ProductUnit.GRAM.value: 'g',
        ProductUnit.LITER.value: 'l',
        ProductUnit.ML.value: 'ml',
    },
    'en': {
        ProductUnit.PIECE.value: 'pcs',
        ProductUnit.KG.value: 'kg',
        ProductUnit.GRAM.value: 'g',
        ProductUnit.LITER.value: 'L',
        ProductUnit.ML.value: 'ml',
    },
}


def _amount_str(amount: Decimal) -> str:
    q = amount.quantize(_THREE)
    if q == q.to_integral_value():
        return str(int(q))
    s = format(q.normalize(), 'f')
    return s.rstrip('0').rstrip('.') if '.' in s else s


def format_size_label(
    product_unit: str,
    unit_amount: Decimal,
    *,
    lang: str = 'ru',
) -> str:
    """Human-readable pack size, e.g. «1 кг», «500 мл», «1 шт»."""
    unit = product_unit or ProductUnit.PIECE.value
    lang = lang if lang in Language.codes() else 'ru'
    short = _UNIT_SHORT.get(lang, _UNIT_SHORT['ru']).get(unit, unit)
    amount = unit_amount if unit_amount and unit_amount > 0 else Decimal('1')

    if unit == ProductUnit.PIECE.value and amount == Decimal('1'):
        return short

    return f'{_amount_str(amount)} {short}'


def enrich_translations_grammage(
    translations: Optional[Dict[str, Dict[str, Any]]],
    product_unit: str,
    unit_amount: Decimal,
) -> Dict[str, Dict[str, Any]]:
    """
    Fill missing/empty grammage per language from product_unit + unit_amount.
    Explicit grammage in request is kept.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for lang, trans in (translations or {}).items():
        if not isinstance(trans, dict) or lang not in Language.codes():
            continue
        row = dict(trans)
        grammage = (row.get('grammage') or '').strip()
        if not grammage:
            row['grammage'] = format_size_label(product_unit, unit_amount, lang=lang)
        out[lang] = row
    if not out:
        for lang in Language.codes():
            out[lang] = {'grammage': format_size_label(product_unit, unit_amount, lang=lang)}
    return out
