"""Reusable OpenAPI path/query parameter descriptions (Swagger)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

# --- Path: buyurtma ---
PARAM_ORDER_ID = OpenApiParameter(
    name='id',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    required=True,
    description=(
        '**Buyurtma ID** (`Order.id`). '
        'Qayerdan: `POST /orders/` yoki `GET /orders/my/` javobidagi `"id": 4`. '
        'Bu mahsulot katalog ID emas.'
    ),
)

# --- Path: buyurtma ichidagi qator (OrderProduct) ---
PARAM_ORDER_LINE_ID = OpenApiParameter(
    name='line_id',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    required=True,
    description=(
        '**Buyurtma qatori ID** (`OrderProduct.id`). '
        'Qayerdan: `GET /orders/{id}/` → `order_products[].id` (masalan `2`). '
        '**`product_id` emas** — katalogdagi mahsulot ID (`product_id`) boshqa maydon.'
    ),
)

PARAM_ADDRESS_ID = OpenApiParameter(
    name='pk',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    required=True,
    description='**Saqlangan manzil ID** (`DeliveryAddress.id`). `GET /addresses/` ro‘yxatidan.',
)

PARAM_DELIVERY_RULE_ID = OpenApiParameter(
    name='pk',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    required=True,
    description='**Qoida ID** (`DeliveryFeeRule.id`).',
)

PARAM_ORDER_STATUS_FILTER = OpenApiParameter(
    name='status',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description='Filtr: `created`, `confirmed`, `picking`, `shipped`, `delivered`, `rejected`, `cancelled`.',
)

PARAM_SLOT_RELATIVE = OpenApiParameter(
    name='relative',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description='`today` yoki `tomorrow`. `date` berilsa e’tiborsiz qolinadi.',
)

PARAM_SLOT_DATE = OpenApiParameter(
    name='date',
    type=OpenApiTypes.DATE,
    location=OpenApiParameter.QUERY,
    required=False,
    description='Yetkazish kuni: `YYYY-MM-DD`.',
)

# Umumiy path parametrlar ro‘yxati
ORDER_PATH_PARAMS = [PARAM_ORDER_ID]
ORDER_LINE_PATH_PARAMS = [PARAM_ORDER_ID, PARAM_ORDER_LINE_ID]
