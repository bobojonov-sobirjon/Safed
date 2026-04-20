# Safed Backend — qo‘shilgan funksiyalar (2026-04-20)

Bu hujjat siz so‘ragan funksiyalar bo‘yicha **hozirgi holat**ni va men qo‘shgan o‘zgarishlarni jamlaydi.

> Eslatma: `README.md` dagi order statuslar (`pending/process/...`) endi eskirdi. Hozirgi statuslar quyida.

---

## 1) Product search (qidiruv)

### Qo‘shildi
- `GET /api/products/?q=...`

### Qidiruv qamrovi
- `Products.unique_id` (icontains)
- `ProductBarcode.barcode` (icontains)
- `ProductsTranslation.name` (icontains)
- `ProductsTranslation.description` (icontains)

### Qo‘shimcha mavjud filterlar (oldindan bor edi)
- `category`, `is_active`, `limit`, `offset`

---

## 2) Admin: active buyurtmalar + statuslarni o‘zgartirish (yangi/yig‘ilyapti/yo‘lda/...)

### Statuslar (yangilandi)
`apps/core/enums.py` dagi `OrderStatus` endi quyidagicha:
- `new` — **yangi**
- `picking` — **yig‘ilyapti**
- `on_the_way` — **yo‘lda**
- `delivered` — **yetkazildi**
- `rejected` — **bekor qilindi (admin/operator)**
- `cancelled` — **bekor qilindi (user)**

### Status o‘zgartirish endpoint (bor edi, yangilandi)
- `PATCH /api/orders/<id>/status/`
  - body: `{ "status": "picking" }` va hokazo

### Active orderlar ro‘yxati (qo‘shildi)
- `GET /api/orders/active/` (staff uchun)

### Order ichidagi tovarlar (oldindan ham bor edi)
`OrderListSerializer` ichida `order_products` bor:
- quantity
- unit_price
- total_price
- product detail (name/translation, rasm, unit, va h.k.)

---

## 3) Narx: +10% servis, dostavka rule, paket/yig‘ish fixed fee, admin yakuniy summa, qaytim

### Qo‘shildi: fee sozlamalari (admin paneldan)
1) **`OrderFeeSettings`** (singleton)
- `service_fee_percent` (default **10%**)
- `packing_fee_amount` (masalan **5000**)

2) **`DeliveryFeeRule`**
Subtotal (tovarlar summasi) bo‘yicha delivery fee:
- `min_order_amount`
- `max_order_amount` (bo‘sh bo‘lsa +inf)
- `fee_amount`
- `is_active`

### Qo‘shildi: order pricing snapshot fieldlar
`Order` modeliga qo‘shilgan:
- `products_subtotal`
- `service_fee_percent`
- `service_fee_amount`
- `delivery_fee`
- `packing_fee`
- `estimated_total`
- `final_total` (admin kiritadi)
- `refund_amount`

### Hisoblash qachon ishlaydi
- Order create paytida (`POST /api/orders/`) pricing hisoblanadi.
- Order update paytida (`PUT /api/orders/<id>/`) pricing qayta hisoblanadi.

### Admin yakuniy summa kiritishi (qo‘shildi)
- `PATCH /api/orders/<id>/finalize-pricing/`
  - body: `{ "final_total": 110000 }`
  - `refund_amount` hisob: `max(estimated_total - final_total, 0)`

> Payment (userdan pul yechish/qaytarish) integratsiyasi bu repoda yo‘q, bu endpoint faqat **hisob-kitob** va “qaytim miqdori”ni chiqarib beradi.

---

## 4) Order create: lat/lon majburiy, podyez/uy raqami/izoh ixtiyoriy

### O‘zgardi (majburiy qilindi)
- `POST /api/orders/` endi quyidagilarni **majburiy** talab qiladi:
  - `lat`
  - `long`
  - `address`

### Qo‘shildi (ixtiyoriy maydonlar)
- `entrance` — podyezd
- `apartment` — uy/xonadon
- `comment` — qo‘shimcha izoh

Bu fieldlar `OrderListSerializer` javobida ham qaytadi.

---

## 5) Driver (Courier) uchun orderlar: manzil, order id, user raqami

### Qo‘shildi
- `GET /api/orders/courier/my/`
  - faqat courier guruhidagi userlar uchun

### Javobda kerakli ma’lumotlar bor
- `id` (order id)
- `address`, `lat`, `long`
- `user_data.phone` (user raqami)

---

## 6) Product “joy/polka” (yig‘ishda ko‘rish uchun)

### Qo‘shildi
- `Products.shelf_location` (masalan: `A-32`)

### API’da chiqadi
- `ProductListSerializer` endi `shelf_location` ni ham qaytaradi.
- Product create/update orqali ham kiritish mumkin (`ProductCreateSerializer`ga qo‘shildi).

---

## 7) Admin panel (Django admin) — orders/products/settings

### Accounts admin tuzatildi
- `apps/accounts/admin.py` da `list_display` ichida `groups` M2M bo‘lgani uchun `admin.E109` xato bo‘layotgan edi.
- Endi `groups_display()` orqali group nomlari string ko‘rinishda chiqadi.

### Orders admin yaxshilandi
- `Order` admin’da:
  - list_display: status, subtotal/fee/estimated/final/refund
  - search: user phone, address
  - inline: `OrderProduct` va `OrderCourier`
- `DeliveryFeeRule` va `OrderFeeSettings` admin paneldan boshqariladi.

### Products admin qo‘shildi
- `Products`, `Badge`, `Unit` admin panelga ulandi.
- `Products` ichida:
  - search: unique_id, shelf_location, translations name, barcode
  - inline: images, barcodes

---

## 8) Migration va system check

### Qo‘shilgan migrationlar
- `apps/orders/migrations/0004_orderfeesettings_order_apartment_order_comment_and_more.py`
- `apps/products/migrations/0006_products_shelf_location_and_more.py`

### Tekshiruv
- `python manage.py check` — **xatosiz**
