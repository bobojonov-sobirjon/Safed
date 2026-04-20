# Safed Backend — Frontend uchun API qo‘llanma (2026-04-20)

Bu fayl frontend (User/Admin/Courier) uchun: **qaysi ekranda qaysi endpoint chaqiriladi**, **qanday request yuboriladi**, **response’dan qaysi fieldlar ishlatiladi**.

> `README.md` dagi eski order statuslar (`pending/process/...`) endi ishlatilmaydi. Hozirgi statuslar: `new`, `picking`, `on_the_way`, `delivered`, `rejected`, `cancelled`.

---

## 1) Product (User ekranlari)

### 1.1) Product list (asosiy katalog)
- **Endpoint**: `GET /api/v1/products/`
- **Query**:
  - `limit`, `offset`
  - `category` (id)
  - `is_active` (true/false)
- **Response (har product)**: `ProductListSerializer`
  - **UI uchun**:
    - `translations` → `name/description/...` (uz/ru/en)
    - `price`, `price_discount`, `is_discount`, `discount_percentage`
    - `quantity`, `is_active`
    - `images[]`
    - `barcodes[]`
    - `category`
    - `is_favourite`
  - **admin yig‘ish uchun**:
    - `shelf_location` (masalan `A-32`)

### 1.2) Product search (qidiruv)
- **Endpoint**: `GET /api/v1/products/?q=...`
- **Qidiradi**:
  - `unique_id`
  - `barcodes.barcode`
  - `translations.name`
  - `translations.description`

### 1.3) Product detail
- **Endpoint**: `GET /api/v1/products/<id>/`
- **Response**: `ProductListSerializer`

---

## 2) Order (User ekranlari)

### 2.1) Order create (checkout)
- **Endpoint**: `POST /api/v1/orders/`
- **Body (JSON)**:
  - **majburiy**:
    - `products_data`: `[{ product_id, quantity, total_price }]`
    - `lat`, `long`, `address`
  - **ixtiyoriy**:
    - `entrance` (podyezd)
    - `apartment` (uy/xonadon)
    - `comment` (izoh)
- **Response**: `OrderListSerializer`
  - **order**: `id`, `status`, `status_display`
  - **manzil**: `address`, `lat`, `long`, `entrance`, `apartment`, `comment`
  - **tovarlar**: `order_products[]` (ichida `product` detail ham bor)
  - **pricing**:
    - `products_subtotal`
    - `service_fee_percent` (default 10)
    - `service_fee_amount`
    - `delivery_fee`
    - `packing_fee`
    - `estimated_total`
    - `final_total` (admin kiritmaguncha null bo‘lishi mumkin)
    - `refund_amount`

### 2.2) Mening orderlarim
- **Endpoint**: `GET /api/v1/orders/my/`
- **Query (ixtiyoriy)**: `status=new|picking|on_the_way|delivered|rejected|cancelled`
- **Response**: `OrderListSerializer[]`

### 2.3) Order detail
- **Endpoint**: `GET /api/v1/orders/<id>/`
- **Response**: `OrderListSerializer`

---

## 3) Admin/Operator ekranlari (orderlar bilan ishlash)

### 3.1) Active orderlar (yig‘iladigan/yo‘ldagi)
- **Endpoint**: `GET /api/v1/orders/active/`
- **Query (ixtiyoriy)**: `status=...`
- **Response**: `OrderListSerializer[]`
- **Yig‘ish ekranida ko‘rsatish**:
  - `order_products[]` ichida:
    - `quantity`
    - `product.translations.name` (nomi)
    - `product.unit` (o‘lchov birligi)
    - `product.shelf_location` (A-32)

### 3.2) Barcha orderlar (admin)
- **Endpoint**: `GET /api/v1/orders/all/`
- **Query**:
  - `status=...`
  - `user=<user_id>`

### 3.3) Status o‘zgartirish (admin/operator/courier)
- **Endpoint**: `PATCH /api/v1/orders/<id>/status/`
- **Body**: `{ "status": "picking" }`
- **Statuslar**:
  - `new` → `picking` → `on_the_way` → `delivered`
  - `rejected`, `cancelled` (holatga qarab)

### 3.4) Admin yakuniy narx kiritishi (order yig‘ilgach)
- **Endpoint**: `PATCH /api/v1/orders/<id>/finalize-pricing/`
- **Body**: `{ "final_total": 110000 }`
- **Natija**:
  - `final_total` set bo‘ladi
  - `refund_amount = max(estimated_total - final_total, 0)`

> Muhim: bu endpoint faqat **hisob-kitob** qiladi. Real payment/refund (pul qaytarish) integratsiyasi alohida bo‘ladi.

---

## 4) Courier (driver) ekranlari

### 4.1) Menga biriktirilgan orderlar
- **Endpoint**: `GET /api/v1/orders/courier/my/`
- **Query (ixtiyoriy)**: `status=...`
- **Response**: `OrderListSerializer[]`
- **Courierga kerakli fieldlar**:
  - `id`
  - `address`, `lat`, `long`
  - `user_data.phone`

---

## 5) Chat (REST + WebSocket)

Chat API `apps/realtime` orqali ishlaydi. HTTP endpointlar `/api/v1/` ostida, WebSocket esa alohida `/ws/` ostida.

### 5.1) Chat room yaratish / ro‘yxat
- **Mening chatlarim**: `GET /api/v1/chat/rooms/`
- **Order uchun chat yaratish** (agar oldin yaratilgan bo‘lsa o‘sha room qaytadi):
  - `POST /api/v1/chat/rooms/`
  - body: `{ "order_id": 123 }`

### 5.2) Order bo‘yicha room topish
- `GET /api/v1/chat/orders/<order_id>/`

### 5.3) Xabarlar tarixini olish
- `GET /api/v1/chat/rooms/<room_id>/messages/`

### 5.4) WebSocket orqali xabar yuborish (real-time chat)
- **WS URL**: `ws://<HOST>/ws/chat/<room_id>/<ACCESS_TOKEN>/`
  - `ACCESS_TOKEN` — login bo‘lgandan keyin olingan JWT access token
- **Yuboriladigan message (misol JSON)**:
  - `{ "message": "Assalomu alaykum" }`

### 5.5) Notification WebSocket (real-time notification)
- **WS URL**: `ws://<HOST>/ws/notifications/<ACCESS_TOKEN>/`
- Qo‘shimcha REST:
  - `GET /api/v1/notifications/`
  - `GET /api/v1/notifications/unread/`
  - `PATCH /api/v1/notifications/read-all/`
  - `PATCH /api/v1/notifications/<id>/read/`

---

## 6) Admin API — fee sozlash (Django admin YO‘Q)

### 6.1) 10% servis va paket/yig‘ish (fixed)
- **Django admin emas, API orqali** (faqat **Super Admin** / **Admin**):
  - `GET /api/v1/admin/fees/settings/`
  - `PATCH /api/v1/admin/fees/settings/`
    - body: `{ "service_fee_percent": 10, "packing_fee_amount": 5000 }`

### 6.2) Dostavka narxi (rule)
- **Django admin emas, API orqali** (faqat **Super Admin** / **Admin**):
  - `GET /api/v1/admin/fees/delivery-rules/` (list)
  - `POST /api/v1/admin/fees/delivery-rules/` (create)
    - body: `{ "min_order_amount": 0, "max_order_amount": 100000, "fee_amount": 10000, "is_active": true }`
  - `PATCH /api/v1/admin/fees/delivery-rules/<id>/` (update)
  - `DELETE /api/v1/admin/fees/delivery-rules/<id>/` (delete)

  **Misol rule lar**:
  - 0 .. 100000 → 10000
  - 100000 .. 200000 → 3000
  - 300000 .. +inf → 0

---

## 7) Qisqa “frontend checklist”

- **Search**: product list ekranda `q` query qo‘shing.
- **Checkout**: order create’da `lat/long/address` majburiy yuboring; qolganlari ixtiyoriy.
- **Admin picking UI**: `orders/active` dan order olib, `order_products[].product.shelf_location` ko‘rsating.
- **Pricing UI**:
  - Userga: `estimated_total` ko‘rsating
  - Admin finalize qilgach: `final_total` va `refund_amount` ko‘rsating
