"""
Create / update product — single entry for API and services.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction

from apps.core.enums import ProductUnit
from apps.products.catalog_units import enrich_translations_grammage
from apps.products.models import Products, ProductImage, ProductBarcode
from apps.products.services.barcode import generate_barcode_number, generate_barcode_image
from apps.products.unit_pricing import unit_amount_for_product


PRODUCT_SCALAR_FIELDS = (
    'shelf_location',
    'quantity',
    'price',
    'price_discount',
    'discount_percentage',
    'is_discount',
    'is_active',
    'product_unit',
    'unit_amount',
)


def apply_product_translations(
    product: Products,
    translations: Optional[Dict[str, Dict[str, Any]]],
    *,
    product_unit: Optional[str] = None,
    unit_amount: Optional[Decimal] = None,
) -> None:
    pu = product_unit or product.product_unit or ProductUnit.PIECE.value
    ua = unit_amount if unit_amount is not None else unit_amount_for_product(product)
    merged = enrich_translations_grammage(translations, pu, ua)
    fields = ['name', 'description', 'composition', 'expiration_date', 'country', 'grammage']

    for lang, trans in merged.items():
        product.set_current_language(lang)
        for field in fields:
            if field in trans:
                setattr(product, field, trans[field] if trans[field] is not None else '')
        product.save()


def assign_product_fields(product: Products, data: Dict[str, Any]) -> None:
    if 'badge' in data:
        product.badge = data['badge']
    if 'unit' in data:
        product.unit = data['unit']
    if 'category' in data and data['category'] is not None:
        product.category = data['category']
    for field in PRODUCT_SCALAR_FIELDS:
        if field in data and data[field] is not None:
            setattr(product, field, data[field])


@transaction.atomic
def create_product_record(
    *,
    translations: Dict[str, Dict[str, Any]],
    category,
    price: Decimal,
    product_unit: str = ProductUnit.PIECE.value,
    unit_amount: Decimal = Decimal('1'),
    quantity: int = 0,
    badge=None,
    unit=None,
    shelf_location: Optional[str] = None,
    price_discount=None,
    discount_percentage: int = 0,
    is_discount: bool = False,
    is_active: bool = True,
    barcode_number: Optional[str] = None,
    images: Optional[List] = None,
) -> Products:
    product = Products(
        badge=badge,
        unit=unit,
        category=category,
        shelf_location=shelf_location or '',
        quantity=quantity,
        price=price,
        price_discount=price_discount,
        discount_percentage=discount_percentage,
        is_discount=is_discount,
        is_active=is_active,
        product_unit=product_unit,
        unit_amount=unit_amount,
    )
    product.save()
    apply_product_translations(
        product, translations, product_unit=product_unit, unit_amount=unit_amount,
    )
    create_product_barcode(product, barcode_number)
    if images:
        for idx, img in enumerate(images):
            ProductImage.objects.create(product=product, image=img, order=idx)
    return product


@transaction.atomic
def update_product_record(
    product: Products,
    *,
    translations: Optional[Dict[str, Dict[str, Any]]] = None,
    **fields,
) -> Products:
    assign_product_fields(product, fields)
    product.save()
    if translations is not None:
        apply_product_translations(
            product,
            translations,
            product_unit=product.product_unit,
            unit_amount=unit_amount_for_product(product),
        )
    return product


def create_product_barcode(product: Products, barcode_number: Optional[str] = None) -> ProductBarcode:
    if not barcode_number:
        barcode_number = generate_barcode_number()
    img_file = generate_barcode_image(barcode_number)
    barcode = ProductBarcode.objects.create(product=product, barcode=barcode_number)
    if img_file:
        barcode.barcode_image.save(f'{barcode_number}.png', img_file, save=True)
    return barcode
