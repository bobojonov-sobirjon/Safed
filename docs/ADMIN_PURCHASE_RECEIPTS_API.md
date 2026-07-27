# Admin Panel — Закупки / Приход API

Alohida admin panel (Django admin emas) uchun **оптовая закупка / приход** hujjatlari.

**Base URL:** `/api/v1/`  
**Auth:** `Authorization: Bearer <access_token>`  
**Ruxsat:** faqat `Admin` yoki `Super Admin`

---

## UI → API mapping

| UI (rasm) | API |
|-----------|-----|
| Yuqori jadval «Закупки» | `GET /inventory/receipts/` |
| Yuqoridagi **Создать** (hujjat) | `POST /inventory/receipts/` |
| Hujjatni tanlash / pastki panel | `GET /inventory/receipts/{id}/` |
| Pastdagi **Создать** (tovar) | `POST /inventory/receipts/{id}/items/` |
| Tovar tahrirlash | `PATCH /inventory/receipts/{id}/items/{item_id}/` |
| Tovar o‘chirish | `DELETE /inventory/receipts/{id}/items/{item_id}/` |
| Umumiy summa (`Сумма`) | response dagi `subtotal` |
| **Провести** | `POST /inventory/receipts/{id}/post/` |
| **Отменить проводку** | `POST /inventory/receipts/{id}/unpost/` |
| Hujjatni o‘chirish (faqat draft) | `DELETE /inventory/receipts/{id}/` |
| Tab **Оплата** | `POST /inventory/receipts/{id}/payment/` |
| Контрагент (поставщик) | `/inventory/suppliers/` |

---

## Statuslar

### Проводка (`status`)

| Qiymat | Ma’nosi | UI |
|--------|---------|-----|
| `draft` | Черновик | hali o‘zgartirish mumkin |
| `posted` | Проведён | skladga qo‘shilgan, tahrir yopiq |
| `cancelled` | Отменён | bekor qilingan |

### Оплата (`payment_status`) — hisoblanadi

| Qiymat | Shart |
|--------|--------|
| `unpaid` | `paid_amount <= 0` |
| `partial` | `0 < paid_amount < subtotal` |
| `paid` | `paid_amount >= subtotal` |

`debt` = `subtotal` − `paid_amount`

---

## 1. Ro‘yxat — «Закупки»

```http
GET /api/v1/inventory/receipts/
```

### Query params

| Param | Misol | Izoh |
|-------|-------|------|
| `status` | `draft` / `posted` / `cancelled` | Проводка filtri («Все» = yubormang) |
| `payment_status` | `unpaid` / `partial` / `paid` | Оплата filtri |
| `supplier` | `1` | Контрагент ID |
| `q` | `Поставщик` | Qidiruv: raqam, izoh, yetkazib beruvchi nomi |
| `date_from` | `2026-07-01` | |
| `date_to` | `2026-07-31` | |
| `limit` | `20` | |
| `offset` | `0` | |

### Response (ro‘yxat — items ichida emas)

```json
{
  "count": 2,
  "limit": 20,
  "offset": 0,
  "results": [
    {
      "id": 2,
      "doc_number": "2",
      "doc_date": "2026-07-23",
      "status": "draft",
      "notes": "",
      "subtotal": "160000.00",
      "paid_amount": "0.00",
      "debt": "160000.00",
      "payment_status": "unpaid",
      "items_count": 2,
      "supplier": 1,
      "supplier_data": {
        "id": 1,
        "name": "Поставщик 1",
        "phone": "",
        "inn": ""
      },
      "created_at": "2026-07-23T15:24:16Z",
      "posted_at": null
    }
  ]
}
```

**UI ustunlari:** Код=`doc_number`, Контрагент=`supplier_data.name`, Дата=`doc_date`, Сумма=`subtotal`, Оплачено=`paid_amount`, Долг=`debt`, Примечание=`notes`.

---

## 2. Hujjat yaratish — yuqoridagi «Создать»

Modal: Дата, Контрагент, Примечание.

```http
POST /api/v1/inventory/receipts/
Content-Type: application/json
```

```json
{
  "supplier_id": 1,
  "doc_date": "2026-07-23",
  "notes": "Оптовая закупка"
}
```

| Maydon | Majburiy | Izoh |
|--------|----------|------|
| `supplier_id` | ✅ | Контрагент (faol поставщик) |
| `doc_date` | ❌ | Default: bugun |
| `doc_number` | ❌ | Default: avto `1`, `2`, `3`… |
| `notes` | ❌ | Примечание |

**201** — hujjat `status: "draft"`, `subtotal: "0.00"`.

---

## 3. Hujjat detali — pastki panel

```http
GET /api/v1/inventory/receipts/{id}/
```

Javobda `items[]` ham bor:

```json
{
  "id": 2,
  "doc_number": "2",
  "doc_date": "2026-07-23",
  "status": "draft",
  "notes": "",
  "subtotal": "160000.00",
  "paid_amount": "0.00",
  "debt": "160000.00",
  "payment_status": "unpaid",
  "items_count": 2,
  "total_quantity": 12,
  "supplier_data": { "id": 1, "name": "Поставщик 1" },
  "items": [
    {
      "id": 10,
      "product": 10000,
      "product_data": { "id": 10000, "name": "COCA-COLA, 355ML", "price": "8000.00" },
      "quantity": 10,
      "purchase_price": "15000.00",
      "sell_price": "18000.00",
      "margin_percent": null,
      "update_catalog_price": true,
      "current_catalog_price": "8000.00",
      "line_total": "150000.00",
      "product_name_snapshot": "COCA-COLA, 355ML",
      "barcode_snapshot": ""
    },
    {
      "id": 11,
      "product": 10001,
      "quantity": 2,
      "purchase_price": "5000.00",
      "sell_price": "5000.00",
      "line_total": "10000.00",
      "update_catalog_price": false
    }
  ]
}
```

**UI:** `Список товаров (N)` → `items_count`, pastki jami miqdor → `total_quantity`, yuqoridagi umumiy summa → `subtotal`.

---

## 4. Hujjat shapkasi (draft)

```http
PATCH /api/v1/inventory/receipts/{id}/
```

```json
{
  "supplier": 1,
  "doc_date": "2026-07-23",
  "doc_number": "2",
  "notes": "Yangilangan izoh"
}
```

Faqat `draft` da.

```http
DELETE /api/v1/inventory/receipts/{id}/
```

Faqat `draft` — 204.

---

## 5. Tovar qo‘shish — pastdagi «Создать»

Modal: товар, Количество, Стоимость, Наценка / Цена реализации, «Изменить тек. цену».

```http
POST /api/v1/inventory/receipts/{id}/items/
Content-Type: application/json
```

```json
{
  "product_id": 10000,
  "quantity": 10,
  "purchase_price": "15000",
  "sell_price": "18000",
  "margin_percent": "20",
  "update_catalog_price": true
}
```

| Maydon | Majburiy | Izoh |
|--------|----------|------|
| `product_id` | ✅ | Mahsulot ID |
| `quantity` | ✅ | ≥ 1 |
| `purchase_price` | ✅ | Стоимость (закуп) |
| `sell_price` | ❌ | Цена реализации |
| `margin_percent` | ❌ | Наценка % — `sell_price` yo‘q bo‘lsa hisoblanadi |
| `update_catalog_price` | ❌ | default `false`. `true` bo‘lsa **провести** da katalog narxi yangilanadi |

**Hisob-kitob (backend):**

- `line_total` = `purchase_price × quantity`
- Agar faqat `margin_percent` berilsa:  
  `sell_price = purchase_price × (1 + margin/100)`
- Agar ikkalasi ham yo‘q: `sell_price` = joriy katalog narxi
- Hujjat `subtotal` = barcha `line_total` yig‘indisi (avto)

**Tahrirlash:**

```http
PATCH /api/v1/inventory/receipts/{id}/items/{item_id}/
```

**O‘chirish:**

```http
DELETE /api/v1/inventory/receipts/{id}/items/{item_id}/
```

Faqat `draft` da. Posted hujjatda 400.

---

## 6. Товар қидириш (modal)

| Maqsad | Endpoint |
|--------|----------|
| Nom bo‘yicha | `GET /api/v1/products/?q=COCA` |
| Shtrixkod | `GET /api/v1/inventory/products/by-barcode/?barcode=4600...` |

---

## 7. Провести — sklad (остаток) +

```http
POST /api/v1/inventory/receipts/{id}/post/
```

**Shartlar:**

- status = `draft`
- kamida 1 ta item

**Effekt:**

1. Har bir qator: `Products.quantity += quantity`
2. Agar `update_catalog_price === true` va `sell_price > 0` → `Products.price = sell_price`
3. status → `posted`, `posted_at` / `posted_by` to‘ldiriladi
4. Shapka va items tahriri yopiladi

**Xato misollari:**

```json
{ "detail": "Документ пустой.", "code": "empty" }
```

```json
{ "detail": "Проведение возможно только из статуса черновик (draft).", "code": "invalid_status" }
```

---

## 8. Отменить проводку

```http
POST /api/v1/inventory/receipts/{id}/unpost/
```

- Faqat `posted`
- Остаток orqaga: `quantity -= ...`
- status → `draft` (yana tahrirlash / qayta провести mumkin)

> **Farq:** `unpost` = проводкани bekor qilish (draft ga qaytish).  
> `cancel` = hujjatni butunlay `cancelled` qilish.

```http
POST /api/v1/inventory/receipts/{id}/cancel/
```

- `draft` → `cancelled` (stock o‘zgarmaydi)
- `posted` → `cancelled` + stock orqaga

---

## 9. Оплата tab

```http
POST /api/v1/inventory/receipts/{id}/payment/
Content-Type: application/json
```

```json
{
  "paid_amount": "50000"
}
```

Javobda:

```json
{
  "subtotal": "160000.00",
  "paid_amount": "50000.00",
  "debt": "110000.00",
  "payment_status": "partial"
}
```

`paid_amount` — hujjat bo‘yicha **jami** to‘langan summa (incremental emas, to‘liq qiymat).

---

## 10. Поставщики (Контрагент)

```http
GET    /api/v1/inventory/suppliers/
POST   /api/v1/inventory/suppliers/
GET    /api/v1/inventory/suppliers/{id}/
PATCH  /api/v1/inventory/suppliers/{id}/
DELETE /api/v1/inventory/suppliers/{id}/   # soft: is_active=false
```

**Create body:**

```json
{
  "name": "Поставщик 1",
  "phone": "+998901112233",
  "contact_person": "Иван",
  "inn": "123456789",
  "address": "Ташкент"
}
```

Dropdown uchun: `GET /inventory/suppliers/?is_active=true`

---

## Tavsiya etilgan frontend flow

```
1. Sahifa ochiladi
   → GET /inventory/receipts/?limit=50

2. «Создать» (yuqori)
   → modal: supplier + date + notes
   → POST /inventory/receipts/
   → ro‘yxatda yangi qator, tanlang

3. Tanlangan hujjat
   → GET /inventory/receipts/{id}/
   → pastki jadval = items
   → header da subtotal / debt

4. «Создать» (pastki) — tovar
   → products search yoki barcode
   → POST .../items/
   → qayta GET detail yoki local state + subtotal yangilash

5. Barcha tovarlar qo‘shilgach
   → «Провести»
   → POST .../post/
   → status=posted, stock oshgan

6. (ixtiyoriy) Оплата
   → POST .../payment/ { paid_amount }
```

### UI holat qoidalari

| `status` | Shapka tahrir | Items CRUD | Провести | Unpost | Delete |
|----------|---------------|------------|----------|--------|--------|
| `draft` | ✅ | ✅ | ✅ (items > 0) | ❌ | ✅ |
| `posted` | ❌ | ❌ | ❌ | ✅ | ❌ |
| `cancelled` | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## Tezkor endpoint jadvali

| Method | Path |
|--------|------|
| GET/POST | `/inventory/receipts/` |
| GET/PATCH/DELETE | `/inventory/receipts/{id}/` |
| POST | `/inventory/receipts/{id}/post/` |
| POST | `/inventory/receipts/{id}/unpost/` |
| POST | `/inventory/receipts/{id}/cancel/` |
| POST | `/inventory/receipts/{id}/payment/` |
| GET/POST | `/inventory/receipts/{id}/items/` |
| PATCH/DELETE | `/inventory/receipts/{id}/items/{item_id}/` |
| GET/POST | `/inventory/suppliers/` |
| GET/PATCH/DELETE | `/inventory/suppliers/{id}/` |
| GET | `/inventory/products/by-barcode/?barcode=` |
| GET | `/products/?q=` (katalog qidiruv) |

---

## Muhim eslatmalar

1. **Sklad** = `Products.quantity` (alohida Warehouse modeli yo‘q).
2. **Провести** dan keyin qatorlar o‘zgarmaydi — avval `unpost`, keyin tahrir.
3. `update_catalog_price` faqat **post** paytida ishlaydi, item saqlanganda emas.
4. Ro‘yxat endpointi `items` ni qaytarmaydi (tezlik); detail qaytaradi.
5. Barcha inventory endpointlar **Admin / Super Admin** talab qiladi.
