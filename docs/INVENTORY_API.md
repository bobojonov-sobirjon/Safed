# Inventory (Ombor) API — qo‘llanma

Bu hujjat **yangi qo‘shilgan ombor (inventory)** API’lar uchun. Hammasi `api/v1` ostida.

## Kirish (auth va role)

- Bu inventory endpointlar **faqat staff** uchun: **Super Admin** va **Admin**.
- Swagger’da endpointlarni ishlatish uchun JWT access token kerak.

---

## 1) Suppliers (Поставщик)

### 1.1 Supplier list
- **GET** `/api/v1/inventory/suppliers/`
- **Response**: supplierlar ro‘yxati.

### 1.2 Supplier create
- **POST** `/api/v1/inventory/suppliers/`
- **Request body (JSON fields)**:
  - `name` (string, required)
  - `phone` (string, optional)
  - `contact_person` (string, optional)
  - `inn` (string, optional)
  - `address` (string, optional)
  - `is_active` (boolean, optional, default true)

### 1.3 Supplier detail
- **GET** `/api/v1/inventory/suppliers/{id}/`

### 1.4 Supplier update
- **PATCH** `/api/v1/inventory/suppliers/{id}/`
- **Request body**: yuqoridagi fieldlardan istalganini yuborasiz (partial).

### 1.5 Supplier deactivate (soft delete)
- **DELETE** `/api/v1/inventory/suppliers/{id}/`
- **Natija**: supplier o‘chmaydi, `is_active=false` bo‘ladi.

### 1.6 Supplier statement (Акт сверка)
- **GET** `/api/v1/inventory/suppliers/{id}/statement/`
- **Query params (optional)**:
  - `date_from` (YYYY-MM-DD)
  - `date_to` (YYYY-MM-DD)
- **Response**:
  - supplier info
  - receipts ro‘yxati
  - `total_amount` (jami kirim summa)

---

## 2) Receipts (Приход документ)

Receipt workflow (UI oqim):
- 1) **Draft receipt header** yaratiladi (sana, doc_number, supplier)
- 2) Receipt ichiga **items** qo‘shiladi (manual / tanlash / barcode)
- 3) Receipt **post** qilinadi → ombor (`Products.quantity`) oshadi → receipt lock bo‘ladi

### 2.1 Receipt list
- **GET** `/api/v1/inventory/receipts/`
- **Query params (optional)**:
  - `status` (`draft|posted|cancelled`)
  - `supplier` (supplier_id)

### 2.2 Receipt create (draft header)
- **POST** `/api/v1/inventory/receipts/`
- **Request body (JSON fields)**:
  - `supplier_id` (int, required)
  - `doc_number` (string, required)
  - `doc_date` (date, required, format: YYYY-MM-DD)
- **Natija**: yangi receipt `status=draft`.

### 2.3 Receipt detail (header + items)
- **GET** `/api/v1/inventory/receipts/{id}/`

### 2.4 Receipt header update (draft only)
- **PATCH** `/api/v1/inventory/receipts/{id}/`
- **Eslatma**: faqat `draft` bo‘lsa update bo‘ladi.
- **Amaliy fieldlar** (tavsiya):
  - `supplier`
  - `doc_number`
  - `doc_date`

### 2.5 Receipt post (provodka)
- **POST** `/api/v1/inventory/receipts/{id}/post/`
- **Ta’siri**:
  - har item bo‘yicha `Products.quantity += item.quantity`
  - receipt `status=posted` bo‘ladi
  - posted bo‘lgandan keyin item/header o‘zgarmaydi

---

## 3) Receipt items (Приход itemlari)

### 3.1 Items list
- **GET** `/api/v1/inventory/receipts/{receipt_id}/items/`

### 3.2 Item create (draft only)
- **POST** `/api/v1/inventory/receipts/{receipt_id}/items/`
- **Request body (JSON fields)**:
  - `product_id` (int, required)
  - `quantity` (int, required, min 1)
  - `purchase_price` (decimal, required) — kelish narxi
  - `sell_price` (decimal, optional) — sotilish narxi
  - `margin_percent` (decimal, optional) — foiz
- **Qoidalar**:
  - `sell_price` yoki `margin_percent` **bittasi** bo‘lsa yetadi
  - agar `margin_percent` yuborilsa → `sell_price` backendda avtomatik hisoblanadi
- **History (audit)**:
  - item ichida `product_name_snapshot` va `barcode_snapshot` saqlanadi (eski receipt buzilmasin)

### 3.3 Item update (draft only)
- **PATCH** `/api/v1/inventory/receipts/{receipt_id}/items/{item_id}/`
- **Request body**: item create dagidek.

### 3.4 Item delete (draft only)
- **DELETE** `/api/v1/inventory/receipts/{receipt_id}/items/{item_id}/`

---

## 4) Barcode (scanner)

### 4.1 Product by barcode (scanner uchun)
- **GET** `/api/v1/inventory/products/by-barcode/?barcode=4600000000012`
- **Response**:
  - `product` → `ProductListSerializer` formatida (rasm, translations, price, shelf_location va h.k.)

### 4.2 Unique barcode generate (productga biriktirish)
- **POST** `/api/v1/products/{product_id}/barcodes/generate/`
- **Request body (optional)**:
  - `length` (int, default 12)
- **Response**:
  - yangi `ProductBarcode` object

---

## 5) Nima uchun snapshot kerak?

Mahsulot “soft delete” bo‘lsa ham yoki nomi o‘zgarsa ham:
- eski “приход” hujjatlarida itemlar **saqlanib qolishi** kerak
- shuning uchun `StockReceiptItem` ichida:
  - `product_name_snapshot`
  - `barcode_snapshot`
saqlanadi.

