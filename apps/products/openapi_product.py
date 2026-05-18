"""OpenAPI field defs for product create/update (multipart)."""
from apps.core.enums import ProductUnit
from apps.products.product_unit_specs import product_unit_openapi_description

_PRODUCT_UNIT_ENUM = [u.value for u in ProductUnit]

PRODUCT_UNIT_FORM_FIELDS = {
    'product_unit': {
        'type': 'string',
        'enum': _PRODUCT_UNIT_ENUM,
        'description': product_unit_openapi_description(),
        'example': ProductUnit.KG.value,
    },
    'unit_amount': {
        'type': 'number',
        'description': (
            'Hajm, uchun `price` berilgan. piece→1; kg/liter→1; ml butilka→500. '
            'Tanlangan `product_unit` bo‘yicha: GET /products/unit-options/'
        ),
        'example': 1,
    },
}

PRODUCT_CREATE_DESCRIPTION = """
**Mahsulot yaratish — asosiy maydonlar**

| Maydon | Vazifa |
|--------|--------|
| `product_unit` | Narx/savat birligi (quyidagi enum) |
| `unit_amount` | Shu birlikdagi hajm (`price` shu pack uchun) |
| `price` | UZS |
| `quantity` | Sklad qoldig‘i |
| `translations.grammage` | Vitrina matni (bo‘sh → avtomatik) |

Batafsil har bir `product_unit` uchun: **GET `/api/v1/products/unit-options/`**
"""
