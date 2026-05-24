"""Swagger / OpenAPI tag names for order flow (sorted for frontend)."""

TAG_DELIVERY_SLOTS = '01 Order — Delivery Slots'
TAG_ADDRESSES = '02 Order — Addresses'
TAG_PRICING_PREVIEW = '03 Order — Pricing Preview'
TAG_CREATE_ORDER = '04 Order — Create Order'
TAG_PAYMENT = '05 Order — Payment'
TAG_MY_ORDERS = '06 Order — My Orders'
TAG_PICKING = '07 Order — Picking'
TAG_ADMIN_OPERATIONS = '08 Order — Admin Operations'
TAG_COURIER = '09 Order — Courier'
TAG_ORDER_DETAIL = '10 Order — Order Detail'
TAG_FEES = '11 Order — Fees Settings'
TAG_STATISTICS = '12 Order — Statistics'

ORDER_OPENAPI_TAGS = [
    {'name': TAG_DELIVERY_SLOTS, 'description': 'Yetkazish vaqtlari: GET soatlik grid (today/tomorrow/date). Admin POST — kun ish vaqti. `/busy-slots/` — shu tag.'},
    {'name': TAG_ADDRESSES, 'description': 'Saqlangan manzillar: ro‘yxat, yaratish, tahrirlash, o‘chirish.'},
    {'name': TAG_PRICING_PREVIEW, 'description': 'Savat narxi (buyurtmasiz): mahsulotlar, slot, loyalty, min order.'},
    {'name': TAG_CREATE_ORDER, 'description': 'Buyurtma yaratish: `payment_type` card/cash, manzil, slot, mahsulotlar.'},
    {'name': TAG_PAYMENT, 'description': 'To‘lov: CLICK `click-payment` (mijoz), `prepare`/`complete` (CLICK server callback).'},
    {'name': TAG_MY_ORDERS, 'description': 'Mijoz: mening buyurtmalarim, bekor qilish.'},
    {'name': TAG_PICKING, 'description': (
        'Yig‘ish (Operator/Admin): buyurtma `confirmed` → `picking` dan keyin haqiqiy vazn/miqdor. '
        'PATCH picking-lines (line_id) yoki POST picking/scan (barcode). Settlement: extra_payment / refund / none.'
    )},
    {'name': TAG_ADMIN_OPERATIONS, 'description': 'Admin: status o‘zgartirish, kuryer, barcha/aktiv buyurtmalar.'},
    {'name': TAG_COURIER, 'description': 'Kuryer: o‘z buyurtmalari.'},
    {'name': TAG_ORDER_DETAIL, 'description': 'Bitta buyurtma: ko‘rish, tahrirlash (created), o‘chirish.'},
    {'name': TAG_FEES, 'description': 'Super Admin/Admin: servis %, packing, min order, delivery rules, hourly capacity.'},
    {'name': TAG_STATISTICS, 'description': 'Super Admin: buyurtmalar statistikasi, top mahsulotlar.'},
]
