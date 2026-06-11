# Safed — Mobile API Documentation (v1)

Production-ready reference for **mobile frontend** developers (Customer app, Staff/Admin app, Courier app).

---

## Table of Contents

1. [General Info](#1-general-info)
2. [Authentication (JWT)](#2-authentication-jwt)
3. [Accounts & Profile](#3-accounts--profile)
4. [FCM Devices](#4-fcm-devices)
5. [Products](#5-products)
6. [Categories](#6-categories)
7. [Checkout, Orders & Delivery](#7-checkout-orders--delivery)
8. [Cashback & Loyalty](#8-cashback--loyalty)
9. [Chat (REST)](#9-chat-rest)
10. [Notifications (REST)](#10-notifications-rest)
11. [News](#11-news)
12. [Admin — Fees, Zones, Cashback](#12-admin--fees-zones-cashback)
13. [Admin — Inventory (Warehouse)](#13-admin--inventory-warehouse)
14. [Admin — Staff & Users](#14-admin--staff--users)
15. [Admin — Statistics](#15-admin--statistics)
16. [WebSocket Protocols](#16-websocket-protocols)
17. [Enums & Constants](#17-enums--constants)
18. [Error Handling](#18-error-handling)
19. [Complete Endpoint Index](#19-complete-endpoint-index)

---

## 1. General Info

| Field | Value |
|-------|-------|
| **Project** | Safed |
| **Framework** | Django 5 + Django REST Framework (DRF) |
| **API version** | `v1` |
| **Content-Type** | `application/json` (except product/category/news image uploads: `multipart/form-data`) |
| **Authentication** | JWT Bearer token (`rest_framework_simplejwt`) |
| **Swagger UI** | `{BASE}/docs/` |
| **ReDoc** | `{BASE}/redoc/` |
| **OpenAPI schema** | `{BASE}/schema/` |

### Base URLs

| Environment | REST Base | WebSocket Base |
|-------------|-----------|----------------|
| **Production** | `https://apies.firepole.ru/api/v1/` | `wss://apies.firepole.ru/` |
| **Staging** | `https://{staging-host}/api/v1/` | `wss://{staging-host}/` |
| **Local dev** | `http://127.0.0.1:8000/api/v1/` | `ws://127.0.0.1:8000/` |

### Authorization Header

All protected endpoints:

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### JWT Token Lifetime

| Token | Lifetime |
|-------|----------|
| **Access** | 7 days |
| **Refresh** | 7 days (`ROTATE_REFRESH_TOKENS = true`) |

> **Note:** There is currently **no** exposed `/auth/token/refresh/` endpoint. Re-login when access expires.

### User Roles (Groups)

| Group | App |
|-------|-----|
| `User` | Customer mobile app |
| `Operator` | Staff app — order processing, barcode restock |
| `Super Admin` | Staff/Admin app — full access + stats |
| `Admin` | Staff/Admin app — admin + inventory |
| `Courier` | Courier app — delivery |

### Pagination

Many list endpoints support:

| Param | Type | Default | Max |
|-------|------|---------|-----|
| `limit` | integer | varies | usually `200` |
| `offset` | integer | `0` | — |

DRF `LimitOffsetPagination` is used on products; some endpoints return `{ count, limit, offset, results }`.

---

## 2. Authentication (JWT)

### 2.1 Customer — Step 1: Send OTP

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/login/` |
| **Auth** | None (public) |

**Body parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `phone` | string | **yes** | — | Phone number, e.g. `"998901234567"` |

**Example request:**
```json
{
  "phone": "998901234567"
}
```

**Success `200`:**
```json
{
  "message": "СМС код отправлен"
}
```

**DEBUG mode:** if SMS fails, response may include `"code": "123456"` for testing.

**Errors `400`:**
```json
{ "phone": ["Обязательное поле."] }
```

---

### 2.2 Customer — Step 2: Verify OTP → JWT

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/verify-otp/` |
| **Auth** | None (public) |

**Body parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `phone` | string | **yes** | Same phone as step 1 |
| `code` | string | **yes** | 6-digit OTP |

**Example request:**
```json
{
  "phone": "998901234567",
  "code": "123456"
}
```

**Success `200`:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "first_name": "",
    "last_name": "",
    "phone": "998901234567",
    "is_active": true,
    "groups": ["User"],
    "loyalty_points": 0,
    "cashback_balance": "0.00",
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```

**Errors `400`:**
```json
{ "detail": "Неверный код" }
```
```json
{ "detail": "Код истёк" }
```

> OTP expires in **2 minutes**, max **3** attempts.

---

### 2.3 Staff Login (Admin / Operator / Courier / Super Admin)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/admin-login/` |
| **Auth** | None (public) |

**Body parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `phone` | string | **yes** | Staff phone |
| `password` | string | **yes** | Staff password |

**Example request:**
```json
{
  "phone": "998901111111",
  "password": "mypassword123"
}
```

**Success `200`:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 5,
    "first_name": "Ali",
    "last_name": "Karimov",
    "phone": "998901111111",
    "is_active": true,
    "groups": ["Operator"],
    "loyalty_points": 0,
    "cashback_balance": "0.00",
    "created_at": "2026-01-01T08:00:00Z"
  }
}
```

**Errors `401`:**
```json
{ "detail": "Неверные данные" }
```

---

### 2.4 Staff — Update Own Credentials

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `/api/v1/auth/admin/update/` |
| **Auth** | JWT required |

**Body parameters (all optional):**

| Field | Type | Required |
|-------|------|----------|
| `phone` | string | no |
| `password` | string | no |

---

## 3. Accounts & Profile

### 3.1 My Profile

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/users/me/` |
| **Auth** | JWT |

**Response `200`:**
```json
{
  "id": 1,
  "first_name": "Ali",
  "last_name": "Karimov",
  "phone": "998901234567",
  "is_active": true,
  "groups": ["User"],
  "loyalty_points": 150,
  "cashback_balance": "12500.00",
  "created_at": "2026-01-15T10:00:00Z"
}
```

### 3.2 Update Profile

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `/api/v1/users/me/update/` |
| **Auth** | JWT |

| Field | Type | Required |
|-------|------|----------|
| `first_name` | string | no |
| `last_name` | string | no |

### 3.3 Change Password (Customer)

**Step 1 — Send OTP:**

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `/api/v1/users/me/password/send-code/` |
| **Auth** | JWT |

**Step 2 — Change password:**

| | |
|---|---|
| **Method** | `PATCH` |
| **URL** | `/api/v1/users/me/password/` |
| **Auth** | JWT |

| Field | Type | Required |
|-------|------|----------|
| `code` | string | **yes** |
| `password` | string | **yes** |

---

## 4. FCM Devices

Register after login to receive push notifications.

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/devices/` | JWT | List my devices |
| `POST` | `/devices/` | JWT | Register device |
| `PUT` | `/devices/` | JWT | Upsert device |
| `PATCH` | `/devices/` | JWT | Deactivate device |

**POST/PUT body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_token` | string | **yes** | FCM token |
| `device_type` | string | **yes** | `android`, `ios`, `web` |

**PATCH body:**

| Field | Type | Required |
|-------|------|----------|
| `device_token` | string | **yes** |
| `is_active` | boolean | no |

**Response `200/201`:**
```json
{
  "id": 1,
  "device_token": "fcm_token_here",
  "device_type": "android",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

---

## 5. Products

### 5.1 Product Unit Options

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/products/unit-options/` |
| **Auth** | None |

Returns metadata for cart UI (`piece`, `kg`, `gram`, `liter`, `ml`).

### 5.2 Product List

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/products/` |
| **Auth** | Optional (JWT adds `is_favourite`) |

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | string | no | — | Search across **all languages** (uz, ru, en): name, description, composition, barcode, unique_id |
| `category` | integer | no | — | Filter by category ID (includes descendants) |
| `is_active` | boolean | no | — | Filter active products |
| `is_discount` | boolean | no | — | Filter discounted products |
| `limit` | integer | no | DRF default | Pagination |
| `offset` | integer | no | `0` | Pagination |

> **Multilingual search:** App language can be `uz`, but user can search in Russian (`Яблоко`) — product will still be found.

**Response item (abbreviated):**
```json
{
  "id": 42,
  "translations": {
    "ru": { "name": "...", "description": "...", "composition": "...", "expiration_date": "...", "country": "...", "grammage": "..." },
    "uz": { ... },
    "en": { ... }
  },
  "badge": { "id": 1, "name": { "ru": { "name": "..." }, "uz": { ... } } },
  "unit": { "id": 1, "name": { ... } },
  "shelf_location": "A-32",
  "quantity": "100.000",
  "price": "25000.00",
  "price_discount": null,
  "discount_percentage": null,
  "is_discount": false,
  "is_active": true,
  "product_unit": "kg",
  "unit_amount": "1.000",
  "size_label": "1 kg",
  "category": { "id": 3, "name": { "ru": "...", "uz": "..." }, "children": [] },
  "barcodes": [{ "id": 1, "barcode": "4601234567890", "is_active": true }],
  "images": [{ "id": 1, "image": "https://apies.firepole.ru/media/...", "is_active": true }],
  "is_favourite": false,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

### 5.3 Product Detail

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/products/{id}/` |
| **Auth** | Optional |

Same shape as list item.

### 5.4 Favorites (Saved Products)

| Method | URL | Auth | Body |
|--------|-----|------|------|
| `GET` | `/saved/` | JWT | — |
| `POST` | `/saved/` | JWT | `{ "product_id": 42 }` |
| `DELETE` | `/saved/{product_id}/` | JWT | — |

### 5.5 Cart Line Format (checkout)

Each item in `products_data[]`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | integer | **yes** | Product ID |
| `quantity` | decimal/string | **yes** | Min `0.001`. Integer for `piece`; decimal for kg/liter |
| `product_unit` | string | no | `piece`, `kg`, `gram`, `liter`, `ml`. Default = product's `product_unit` |

```json
{
  "products_data": [
    { "product_id": 42, "quantity": "2", "product_unit": "piece" },
    { "product_id": 15, "quantity": "1.5", "product_unit": "kg" }
  ]
}
```

### 5.6 Admin Product CRUD (Staff)

| Method | URL | Auth | Content-Type |
|--------|-----|------|--------------|
| `POST` | `/products/` | JWT | `multipart/form-data` |
| `PUT` | `/products/{id}/` | JWT | `multipart/form-data` |
| `DELETE` | `/products/{id}/` | JWT | — |
| `POST` | `/products/{id}/barcodes/generate/` | JWT | JSON |
| `PATCH` | `/product-barcodes/{id}/` | JWT | JSON |
| `PATCH` | `/product-images/{id}/` | JWT | `multipart/form-data` |

Product create requires `translations` (JSON string in FormData), `category`, `price`, `product_unit`, `unit_amount`.

---

## 6. Categories

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/categories/home/` | Public | Home screen categories |
| `GET` | `/categories/` | Public | Full tree |
| `GET` | `/categories/{id}/` | Public | Detail |
| `POST` | `/categories/` | JWT (Admin) | Create root (`multipart/form-data`) |
| `POST` | `/categories/child/` | JWT (Admin) | Create child |
| `PUT` | `/categories/{id}/` | JWT (Admin) | Update |
| `DELETE` | `/categories/{id}/` | JWT (Admin) | Soft delete |

**List query params:** `parent`, `category`, `name`, `is_active`

---

## 7. Checkout, Orders & Delivery

### 7.1 Order Status Flow

```
created → confirmed → picking → shipped → delivered → completed
                ↓         ↓         ↓
            rejected   rejected   rejected
                ↓
            cancelled (customer, only at created)
```

| Status | Meaning |
|--------|---------|
| `created` | Placed, awaiting payment/confirmation |
| `confirmed` | Accepted by staff |
| `picking` | Warehouse picking |
| `shipped` | Courier on the way |
| `delivered` | At customer address |
| `completed` | Cash: after QR confirm. Card: effectively done at `delivered`+paid |
| `rejected` | Rejected by staff |
| `cancelled` | Cancelled by customer |

### 7.2 Payment Types

| Type | Flow |
|------|------|
| `card` | Create → Click payment → auto `confirmed`+`paid` → staff → `delivered` |
| `cash` | Create → staff notified → `delivered` → QR confirm → `completed`+`paid` |

---

### 7.3 Pricing Preview

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/checkout/pricing-preview/` |
| **Auth** | JWT |

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `products_data` | array | **yes** | — | Cart lines (min 1) |
| `delivery_date` | date | no | — | `YYYY-MM-DD` (all 3 delivery fields together) |
| `delivery_time_start` | string | no | — | `"HH:MM"` |
| `delivery_time_end` | string | no | — | `"HH:MM"` |
| `loyalty_points_to_use` | integer | no | `0` | Max 50% of base, capped by balance |

**Response includes:** `products_subtotal`, `service_fee_amount`, `delivery_fee`, `packing_fee`, `buffer_amount`, `estimated_total`, `can_checkout`, `loyalty_points_applied`, `loyalty_discount_amount`, `loyalty_max_money`.

---

### 7.4 Delivery Slots

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/checkout/delivery-slots/` |
| **Auth** | JWT |

**Query (one of):**

| Param | Type | Description |
|-------|------|-------------|
| `relative` | string | `today` (default) or `tomorrow` |
| `date` | string | `YYYY-MM-DD` |

**Alias:** `GET /api/v1/busy-slots/` — same endpoint.

**Admin POST** (Admin/Super Admin only): configure working hours for a day.

---

### 7.5 Delivery Zone Check

Before checkout, verify address is in delivery zone.

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/checkout/delivery-zone/check/` |
| **Auth** | JWT |

| Param | Type | Required |
|-------|------|----------|
| `lat` | decimal | **yes** |
| `long` | decimal | **yes** |

**Response `200`:**
```json
{
  "allowed": true,
  "message": "",
  "nearest_zone_id": 1,
  "distance_m": 1250.5
}
```

If no active zones configured → `allowed: true` always.

---

### 7.6 Saved Addresses

| Method | URL | Auth |
|--------|-----|------|
| `GET` | `/addresses/` | JWT |
| `POST` | `/addresses/` | JWT |
| `GET` | `/addresses/{id}/` | JWT |
| `PATCH` | `/addresses/{id}/` | JWT |
| `DELETE` | `/addresses/{id}/` | JWT |

**Create body:**

| Field | Type | Required |
|-------|------|----------|
| `street` | string | **yes** |
| `house_number` | string | no |
| `apartment` | string | no |
| `entrance` | string | no |
| `floor` | string | no |
| `intercom_code` | string | no |
| `lat` | decimal | no |
| `long` | decimal | no |
| `label` | string | no |
| `is_default` | boolean | no |

---

### 7.7 Create Order

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/orders/` |
| **Auth** | JWT |

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `products_data` | array | **yes** | Min 1 cart line |
| `payment_type` | string | **yes** | `card` or `cash` |
| `delivery_address_id` | integer | conditional | Saved address ID **OR** `lat`+`long`+`address` |
| `lat` | decimal | conditional | Latitude |
| `long` | decimal | conditional | Longitude |
| `address` | string | conditional | Address text |
| `delivery_date` | date | optional | All 3 delivery fields together |
| `delivery_time_start` | string | optional | `"HH:MM"` |
| `delivery_time_end` | string | optional | `"HH:MM"` |
| `loyalty_points_to_use` | integer | no | Default `0` |
| `leave_at_door` | boolean | no | Default `false` |
| `comment` | string | no | Max 5000 |
| `entrance` | string | no | Max 50 |
| `apartment` | string | no | Max 50 |

**Zone validation:** If active delivery zones exist, address must be within radius → else `400`.

**Example:**
```json
{
  "products_data": [
    { "product_id": 42, "quantity": "2", "product_unit": "piece" }
  ],
  "delivery_address_id": 3,
  "delivery_date": "2026-06-20",
  "delivery_time_start": "10:00",
  "delivery_time_end": "11:00",
  "payment_type": "card",
  "loyalty_points_to_use": 0,
  "leave_at_door": false,
  "comment": "Call before arrival"
}
```

---

### 7.8 Card Payment (CLICK)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/orders/{id}/click-payment/` |
| **Auth** | JWT |

| Field | Type | Required |
|-------|------|----------|
| `return_url` | string | no |

**Response:**
```json
{
  "order_id": 8,
  "amount": "125000.00",
  "merchant_trans_id": "ORDER-8-...",
  "payment_url": "https://my.click.uz/..."
}
```

---

### 7.9 Customer Order Actions

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/orders/my/` | My orders (`?status=shipped`) |
| `GET` | `/orders/{id}/` | Order detail |
| `PUT` | `/orders/{id}/` | Update (`created` only) |
| `DELETE` | `/orders/{id}/` | Delete (`created` only) |
| `GET` | `/orders/cancel-reasons/` | Cancel reasons list |
| `POST` | `/orders/{id}/cancel/` | Cancel (`created` only) |
| `GET` | `/orders/{id}/cash-qr-image/` | Cash QR PNG |
| `POST` | `/orders/{id}/delivery-response/` | Accept/reject delivery |

**Cancel body:**

| Field | Type | Required |
|-------|------|----------|
| `reason_ids` | integer[] | no |
| `comment` | string | no |

At least one of `reason_ids` (non-empty) or `comment` (non-empty) required.

**Delivery response body:**

| Field | Type | Required |
|-------|------|----------|
| `accepted` | boolean | **yes** |

---

### 7.10 Staff Order Actions

| Method | URL | Role | Description |
|--------|-----|------|-------------|
| `GET` | `/orders/all/` | Staff | All orders |
| `GET` | `/orders/active/` | Staff | Active orders |
| `PATCH` | `/orders/{id}/status/` | Staff/Courier | Change status |
| `POST` | `/orders/{id}/add-courier/` | Staff | Assign courier |
| `PATCH` | `/orders/{id}/picking-lines/{line_id}/` | Staff | Adjust picking qty |
| `POST` | `/orders/{id}/picking/scan/` | Staff | Barcode scan |

**Status transitions:**

| From | Allowed to |
|------|------------|
| `created` | `confirmed`, `rejected`, `cancelled` |
| `confirmed` | `picking`, `rejected`, `cancelled` |
| `picking` | `shipped`, `rejected`, `cancelled` |
| `shipped` | `delivered`, `rejected` |
| `delivered` | *(none via status API)* |
| `completed` | *(only via cash QR confirm)* |

**Add courier body:** `{ "courier_id": 12 }` — order must be `picking` → auto `shipped`.

**Picking scan body:** `{ "barcode": "4601234567890" }`

**Picking line body:** `{ "quantity": "1.250" }` — `line_id` = `OrderProduct.id`.

---

### 7.11 Courier Actions

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/orders/courier/my/` | My orders (`?status=shipped`) |
| `PATCH` | `/orders/{id}/status/` | Mark `delivered` |
| `PATCH` | `/orders/cash/confirm/` | Cash QR confirm |

**Cash confirm body:**

| Field | Type | Required |
|-------|------|----------|
| `order_id` | integer | **yes** |
| `qr_code` | string | **yes** |

Result: `status` → `completed`, `payment_status` → `paid`, stock deducted, cashback accrued.

---

### 7.12 Order Response Structure

```json
{
  "id": 8,
  "user_data": { "id": 1, "phone": "998...", "first_name": "", "last_name": "" },
  "status": "shipped",
  "status_display": "Shipped",
  "can_user_cancel": false,
  "order_pricing": {
    "products_subtotal": "95000.00",
    "service_fee_amount": "4750.00",
    "delivery_fee": "15000.00",
    "packing_fee": "2000.00",
    "estimated_total": "121750.00",
    "final_total": null,
    "payment_type": "cash",
    "payment_status": "pending",
    "loyalty_points_used": 0,
    "loyalty_discount_amount": "0.00"
  },
  "delivery_slot": {
    "date": "2026-06-20",
    "time_start": "10:00",
    "time_end": "11:00",
    "address": "...",
    "lat": "41.311081",
    "long": "69.240562"
  },
  "order_products": [ /* lines */ ],
  "order_couriers": [ /* couriers */ ],
  "cash_qr_code": null,
  "cash_qr_image_url": null,
  "created_at": "...",
  "updated_at": "..."
}
```

---

## 8. Cashback & Loyalty

### 8.1 Loyalty Points (spend at checkout)

- User field: `loyalty_points` (integer)
- Spend via `loyalty_points_to_use` in order/preview
- Max discount: **50%** of pre-loyalty total
- Refunded on customer cancel

### 8.2 Cashback Balance (earn on completed orders)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/users/me/cashback/` |
| **Auth** | JWT |

**Response:**
```json
{
  "cashback_balance": "12500.00",
  "cashback_percent": "5.00",
  "cashback_active": true
}
```

### 8.3 Cashback History

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/users/me/cashback/history/` |
| **Auth** | JWT |

**Response:** array of transactions:
```json
[
  {
    "id": 1,
    "order": 8,
    "amount": "5000.00",
    "transaction_type": "earned",
    "balance_after": "12500.00",
    "note": "Order #8",
    "created_at": "2026-06-11T10:00:00Z"
  }
]
```

Cashback is accrued when order completes (cash QR confirm or card `delivered`).

---

## 9. Chat (REST)

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/chat/rooms/` | JWT | My chat rooms |
| `POST` | `/chat/rooms/` | JWT | Create `{ "order_id": 8 }` |
| `GET` | `/chat/rooms/{id}/` | JWT | Room detail |
| `DELETE` | `/chat/rooms/{id}/` | JWT | Close room |
| `GET` | `/chat/orders/{order_id}/` | JWT | Room by order |
| `GET` | `/chat/rooms/{room_id}/messages/` | JWT | Message history |
| `PATCH` | `/chat/rooms/{room_id}/read/` | JWT | Mark read |

> Send messages via **WebSocket only** (not REST POST).

---

## 10. Notifications (REST)

| Method | URL | Role |
|--------|-----|------|
| `GET` | `/notifications/` | Auto by role |
| `GET` | `/notifications/customer/` | Customer |
| `GET` | `/notifications/staff/` | Operator/SA |
| `GET` | `/notifications/courier/` | Courier |
| `GET` | `/notifications/unread/` | All |
| `PATCH` | `/notifications/{id}/read/` | All → `204` |
| `PATCH` | `/notifications/read-all/` | All |

**Query params:** `is_read`, `type`, `limit` (max 100), `offset`, `audience`

**Response:**
```json
{
  "audience": "customer",
  "unread_count": 2,
  "count": 15,
  "limit": 50,
  "offset": 0,
  "results": [
    {
      "id": 55,
      "title": "Заказ в пути",
      "body": "...",
      "type": "order_status",
      "data": { "order_id": 8 },
      "is_read": false,
      "created_at": "2026-05-19T10:00:00Z"
    }
  ]
}
```

---

## 11. News

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/posts/` | Public | News feed |
| `GET` | `/posts/{id}/` | Public | Post detail |
| `POST` | `/posts/create/` | JWT (Admin) | Create post |
| `PUT` | `/posts/{id}/update/` | JWT (Admin) | Update |
| `DELETE` | `/posts/{id}/delete/` | JWT (Admin) | Delete |

---

## 12. Admin — Fees, Zones, Cashback

**Role:** `Admin` or `Super Admin`

### 12.1 Fee Settings (singleton)

| Method | URL |
|--------|-----|
| `GET` | `/admin/fees/settings/` |
| `PATCH` | `/admin/fees/settings/` |

| Field | Type | Description |
|-------|------|-------------|
| `service_fee_percent` | decimal | Service fee % on products subtotal |
| `packing_fee_amount` | decimal | Fixed packing fee |
| `min_order_subtotal` | decimal | Min order amount (default 1000 UZS) |
| `weight_buffer_percent` | decimal | Weight buffer % |
| `loyalty_point_currency_value` | decimal | UZS per 1 loyalty point |
| `hourly_delivery_capacity` | integer | Max orders per hour slot |

### 12.2 Delivery Fee Rules

| Method | URL |
|--------|-----|
| `GET` | `/admin/fees/delivery-rules/` |
| `POST` | `/admin/fees/delivery-rules/` |
| `PATCH` | `/admin/fees/delivery-rules/{id}/` |
| `DELETE` | `/admin/fees/delivery-rules/{id}/` |

| Field | Type | Required |
|-------|------|----------|
| `min_order_amount` | decimal | **yes** |
| `max_order_amount` | decimal | no |
| `fee_amount` | decimal | **yes** |
| `is_active` | boolean | no |

### 12.3 Delivery Zones

| Method | URL |
|--------|-----|
| `GET` | `/admin/delivery-zones/` |
| `POST` | `/admin/delivery-zones/` |
| `PATCH` | `/admin/delivery-zones/{id}/` |
| `DELETE` | `/admin/delivery-zones/{id}/` |

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | no | Zone label |
| `address` | string | **yes** | Center address text |
| `lat` | decimal | **yes** | Center latitude |
| `long` | decimal | **yes** | Center longitude |
| `radius_m` | integer | **yes** | Radius in meters |
| `is_active` | boolean | no | Default `true` |

### 12.4 Cashback Settings (singleton)

| Method | URL |
|--------|-----|
| `GET` | `/admin/cashback/settings/` |
| `PATCH` | `/admin/cashback/settings/` |

| Field | Type | Description |
|-------|------|-------------|
| `cashback_percent` | decimal | % of order total |
| `is_active` | boolean | Enable/disable accrual |

### 12.5 Cashback Transactions (admin)

| Method | URL |
|--------|-----|
| `GET` | `/admin/cashback/transactions/?user_id=` |

---

## 13. Admin — Inventory (Warehouse)

**Role:** `Admin` or `Super Admin` (except barcode restock: `Operator` or `Super Admin`)

### 13.1 Suppliers (Поставщики)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/inventory/suppliers/` | List (`?is_active=`, `?q=`, `?limit=`, `?offset=`) |
| `POST` | `/inventory/suppliers/` | Create |
| `GET` | `/inventory/suppliers/{id}/` | Detail |
| `PATCH` | `/inventory/suppliers/{id}/` | Update |
| `DELETE` | `/inventory/suppliers/{id}/` | Soft delete (`is_active=false`) |

**Create/Update body:**

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | string | **yes** | — |
| `phone` | string | no | `""` |
| `contact_person` | string | no | `""` |
| `inn` | string | no | `""` |
| `address` | string | no | `""` |
| `is_active` | boolean | no | `true` |

### 13.2 Supplier Statement (Акт сверки — quick report)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/inventory/suppliers/{id}/statement/` |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `date_from` | date | — | `YYYY-MM-DD` |
| `date_to` | date | — | `YYYY-MM-DD` |
| `status` | string | `posted` | `draft`, `posted`, `cancelled`, `all` |
| `opening_balance` | decimal | `0` | Opening debt to supplier |

**Response:**
```json
{
  "supplier": { /* Supplier */ },
  "date_from": "2026-06-01",
  "date_to": "2026-06-30",
  "status_filter": "posted",
  "opening_balance": "5000.00",
  "total_receipts": 3,
  "total_amount": "240000.00",
  "closing_balance": "245000.00",
  "receipts": [ /* StockReceipt[] */ ]
}
```

### 13.3 Stock Receipts (Приход)

**Workflow:** Draft header → Add items → Post → stock increases

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/inventory/receipts/` | List (`?status=`, `?supplier=`, `?date_from=`, `?date_to=`) |
| `POST` | `/inventory/receipts/` | Create draft |
| `GET` | `/inventory/receipts/{id}/` | Detail + items |
| `PATCH` | `/inventory/receipts/{id}/` | Update header (draft only) |
| `POST` | `/inventory/receipts/{id}/post/` | Post → increase stock |
| `POST` | `/inventory/receipts/{id}/cancel/` | Cancel (reverses stock if posted) |

**Create draft body:**

| Field | Type | Required |
|-------|------|----------|
| `supplier_id` | integer | **yes** |
| `doc_number` | string | **yes** (unique) |
| `doc_date` | date | **yes** |

**Receipt item (POST/PATCH `/inventory/receipts/{id}/items/`):**

| Field | Type | Required |
|-------|------|----------|
| `product_id` | integer | **yes** |
| `quantity` | integer | **yes** (min 1) |
| `purchase_price` | decimal | **yes** |
| `sell_price` | decimal | no* |
| `margin_percent` | decimal | no* |

\* One of `sell_price` or `margin_percent` required.

**On post:** `Products.quantity` increases, `Products.price` updated from `sell_price`.

### 13.4 Reconciliation Acts (formal акт сверки)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/inventory/reconciliation-acts/` | List |
| `POST` | `/inventory/reconciliation-acts/` | Create draft |
| `GET` | `/inventory/reconciliation-acts/{id}/` | Detail + receipts |
| `PATCH` | `/inventory/reconciliation-acts/{id}/` | Update draft |
| `DELETE` | `/inventory/reconciliation-acts/{id}/` | Delete draft |
| `POST` | `/inventory/reconciliation-acts/{id}/confirm/` | Confirm & lock |

**Create body:**

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `supplier_id` | integer | **yes** | — |
| `period_from` | date | **yes** | — |
| `period_to` | date | **yes** | — |
| `opening_balance` | decimal | no | `0.00` |
| `notes` | string | no | `""` |

### 13.5 Barcode Tools

| Method | URL | Role | Description |
|--------|-----|------|-------------|
| `GET` | `/inventory/products/by-barcode/?barcode=` | Admin | Lookup product |
| `POST` | `/inventory/products/restock/` | Operator/SA | Quick restock |

**Restock body:** `{ "barcode": "...", "quantity": 50 }`

---

## 14. Admin — Staff & Users

| Method | URL | Role | Description |
|--------|-----|------|-------------|
| `POST` | `/staff/create/` | Super Admin | Create Admin/Operator/Courier |
| `GET` | `/users/group/users/` | Staff | All customers |
| `GET` | `/staff/admins/` | Staff | Admins list |
| `GET` | `/staff/operators/` | Staff | Operators list |
| `GET` | `/staff/couriers/` | Staff | Couriers list |
| `GET` | `/users/{id}/` | Staff | User detail |
| `PATCH` | `/users/{id}/update/` | Staff | Update user |
| `DELETE` | `/users/{id}/delete/` | Staff | Delete/deactivate |
| `PATCH` | `/users/{id}/password/` | Staff | Reset password |

**Staff create body:**

| Field | Type | Required |
|-------|------|----------|
| `phone` | string | **yes** |
| `password` | string | **yes** |
| `group` | string | **yes** | `Admin`, `Operator`, `Courier` |
| `first_name` | string | no |
| `last_name` | string | no |

---

## 15. Admin — Statistics

**Role:** `Super Admin`

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/overview/` | Business overview stats |
| `GET` | `/products/` | Product sales stats |

**Query params:** `period` (`day`, `week`, `month`), `date_from`, `date_to`

---

## 16. WebSocket Protocols

Production: `wss://apies.firepole.ru/`

JWT passed **in URL** (not header).

### 16.1 Notifications

```
wss://apies.firepole.ru/ws/notifications/{access_token}/
```

On connect → `type: "unread_list"`. New → `type: "notification"`. Close `4001` = invalid JWT.

### 16.2 Chat

```
wss://apies.firepole.ru/ws/chat/{room_id}/{access_token}/
```

Send: `{ "action": "message", "message": "Hello" }`  
Read: `{ "action": "read" }`  
Typing: `{ "action": "typing", "is_typing": true }`

### 16.3 Cash Delivery

```
wss://apies.firepole.ru/ws/orders/delivery/{access_token}/
```

Customer accept: `{ "action": "accept_delivery", "order_id": 8 }`  
Server event: `type: "courier_confirmed_cash_payment"`

---

## 17. Enums & Constants

### OrderStatus
`created`, `confirmed`, `picking`, `shipped`, `delivered`, `completed`, `rejected`, `cancelled`

### PaymentType
`card`, `cash`

### PaymentStatus
`pending`, `authorized`, `paid`, `failed`, `refunded`

### ProductUnit
`piece`, `kg`, `gram`, `liter`, `ml`

### DeviceType
`android`, `ios`, `web`

### ReceiptStatus
`draft`, `posted`, `cancelled`

### ReconciliationActStatus
`draft`, `confirmed`

### Languages
`ru`, `uz`, `en` — translations returned in all languages in `translations` object

---

## 18. Error Handling

**Validation `400`:**
```json
{ "field_name": ["Error message"] }
```

**Permission `403`:**
```json
{ "detail": "Доступ запрещён" }
```

**Not found `404`:**
```json
{ "detail": "Не найден" }
```

**Business logic `400` (with code):**
```json
{
  "detail": "Адрес вне зоны доставки.",
  "code": "outside_delivery_zone"
}
```

**Insufficient stock `400`:**
```json
{
  "detail": "Недостаточно товара на складе",
  "insufficient_stock": [
    { "product_id": 42, "requested": "5", "available": "2" }
  ]
}
```

---

## 19. Complete Endpoint Index

### Auth
| Method | Path |
|--------|------|
| POST | `/auth/login/` |
| POST | `/auth/verify-otp/` |
| POST | `/auth/admin-login/` |
| PUT | `/auth/admin/update/` |

### Users & Devices
| Method | Path |
|--------|------|
| GET | `/users/me/` |
| PUT | `/users/me/update/` |
| PUT | `/users/me/password/send-code/` |
| PATCH | `/users/me/password/` |
| GET | `/users/me/cashback/` |
| GET | `/users/me/cashback/history/` |
| GET/POST/PUT/PATCH | `/devices/` |
| POST | `/staff/create/` |
| GET | `/users/group/users/` |
| GET | `/staff/admins/` |
| GET | `/staff/operators/` |
| GET | `/staff/couriers/` |
| GET/PATCH/DELETE | `/users/{id}/` |

### Products
| Method | Path |
|--------|------|
| GET | `/products/unit-options/` |
| GET/POST | `/products/` |
| GET/PUT/DELETE | `/products/{id}/` |
| POST | `/products/{id}/barcodes/generate/` |
| GET/POST/DELETE | `/saved/` |
| GET/PATCH | `/badges/`, `/units/`, `/product-barcodes/{id}/`, `/product-images/{id}/` |

### Categories
| Method | Path |
|--------|------|
| GET | `/categories/home/` |
| GET/POST | `/categories/` |
| POST | `/categories/child/` |
| GET/PUT/DELETE | `/categories/{id}/` |

### Orders & Checkout
| Method | Path |
|--------|------|
| POST | `/checkout/pricing-preview/` |
| GET/POST | `/checkout/delivery-slots/` |
| GET | `/checkout/delivery-zone/check/` |
| GET/POST | `/addresses/` |
| GET/PATCH/DELETE | `/addresses/{id}/` |
| POST | `/orders/` |
| GET | `/orders/my/` |
| GET/PUT/DELETE | `/orders/{id}/` |
| GET | `/orders/cancel-reasons/` |
| POST | `/orders/{id}/cancel/` |
| POST | `/orders/{id}/click-payment/` |
| GET | `/orders/{id}/cash-qr-image/` |
| POST | `/orders/{id}/delivery-response/` |
| GET | `/orders/all/`, `/orders/active/` |
| PATCH | `/orders/{id}/status/` |
| POST | `/orders/{id}/add-courier/` |
| PATCH | `/orders/{id}/picking-lines/{line_id}/` |
| POST | `/orders/{id}/picking/scan/` |
| GET | `/orders/courier/my/` |
| PATCH | `/orders/cash/confirm/` |

### Admin Config
| Method | Path |
|--------|------|
| GET/PATCH | `/admin/fees/settings/` |
| GET/POST | `/admin/fees/delivery-rules/` |
| PATCH/DELETE | `/admin/fees/delivery-rules/{id}/` |
| GET/POST | `/admin/delivery-zones/` |
| PATCH/DELETE | `/admin/delivery-zones/{id}/` |
| GET/PATCH | `/admin/cashback/settings/` |
| GET | `/admin/cashback/transactions/` |

### Inventory
| Method | Path |
|--------|------|
| GET/POST | `/inventory/suppliers/` |
| GET/PATCH/DELETE | `/inventory/suppliers/{id}/` |
| GET | `/inventory/suppliers/{id}/statement/` |
| GET/POST | `/inventory/receipts/` |
| GET/PATCH | `/inventory/receipts/{id}/` |
| POST | `/inventory/receipts/{id}/post/` |
| POST | `/inventory/receipts/{id}/cancel/` |
| GET/POST | `/inventory/receipts/{id}/items/` |
| PATCH/DELETE | `/inventory/receipts/{id}/items/{item_id}/` |
| GET/POST/PATCH/DELETE | `/inventory/reconciliation-acts/` |
| POST | `/inventory/reconciliation-acts/{id}/confirm/` |
| GET | `/inventory/products/by-barcode/` |
| POST | `/inventory/products/restock/` |

### Chat & Notifications
| Method | Path |
|--------|------|
| GET/POST | `/chat/rooms/` |
| GET/DELETE | `/chat/rooms/{id}/` |
| GET | `/chat/orders/{order_id}/` |
| GET | `/chat/rooms/{room_id}/messages/` |
| PATCH | `/chat/rooms/{room_id}/read/` |
| GET | `/notifications/` |
| GET | `/notifications/customer/`, `/staff/`, `/courier/` |
| GET | `/notifications/unread/` |
| PATCH | `/notifications/{id}/read/`, `/notifications/read-all/` |

### News & Stats
| Method | Path |
|--------|------|
| GET | `/posts/`, `/posts/{id}/` |
| POST/PUT/DELETE | `/posts/create/`, `/posts/{id}/update/`, `/posts/{id}/delete/` |
| GET | `/overview/`, `/products/` (stats) |

---

## Quick Reference — Production

```
REST:  https://apies.firepole.ru/api/v1/
WS:    wss://apies.firepole.ru/ws/notifications/{JWT}/
WS:    wss://apies.firepole.ru/ws/chat/{room_id}/{JWT}/
WS:    wss://apies.firepole.ru/ws/orders/delivery/{JWT}/
Docs:  https://apies.firepole.ru/docs/
```

---

*Safed Mobile API v1 — last updated: June 2026*
