# Safed — Mobile API Documentation (v1)

Production-ready reference for **mobile frontend** developers.

---

## Table of Contents

1. [General Info](#1-general-info)
2. [Authentication (JWT)](#2-authentication-jwt)
3. [Product API — What's New](#3-product-api--whats-new)
4. [Order System — Full Flow by Role](#4-order-system--full-flow-by-role)
5. [Push Notifications & FCM Devices](#5-push-notifications--fcm-devices)
6. [WebSocket Protocols](#6-websocket-protocols)
7. [Accounts & Profile](#7-accounts--profile)
8. [Categories](#8-categories)
9. [Checkout & Addresses](#9-checkout--addresses)
10. [Orders — All REST Endpoints](#10-orders--all-rest-endpoints)
11. [Chat (REST)](#11-chat-rest)
12. [Notifications (REST)](#12-notifications-rest)
13. [News](#13-news)
14. [Enums & Constants](#14-enums--constants)
15. [Error Handling](#15-error-handling)

---

## 1. General Info

| Field | Value |
|-------|-------|
| **Project** | Safed |
| **Framework** | Django + Django REST Framework |
| **API version** | `v1` |
| **Content-Type** | `application/json` (except product/admin image uploads: `multipart/form-data`) |
| **Authentication** | JWT Bearer token |
| **Swagger UI** | `{BASE}/docs/` |
| **ReDoc** | `{BASE}/redoc/` |

### Base URLs

| Environment | REST Base | WebSocket Base |
|-------------|-----------|----------------|
| **Production** | `https://apies.firepole.ru/api/v1/` | `wss://apies.firepole.ru/` |
| **Staging** | *(deploy URL)* `/api/v1/` | `wss://{host}/` |
| **Local dev** | `http://127.0.0.1:8000/api/v1/` | `ws://127.0.0.1:8000/` |

### Authorization Header

All protected endpoints require:

```
Authorization: Bearer <access_token>
```

### JWT Token Lifetime

- **Access token:** 7 days
- **Refresh token:** 7 days (issued on login; `ROTATE_REFRESH_TOKENS = true`)
- **Note:** There is currently **no** `/auth/token/refresh/` endpoint exposed. Re-login when access expires.

### User Roles (Groups)

| Group | Mobile app |
|-------|------------|
| `User` | Customer app |
| `Operator` | Staff app — order processing |
| `Super Admin` | Staff app — full access + stats |
| `Admin` | Staff app — admin operations |
| `Courier` | Courier app — delivery |

---

## 2. Authentication (JWT)

### 2.1 Customer Login — Step 1: Send OTP

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/login/` |
| **Auth** | None (public) |

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `phone` | string | **yes** | Phone number, e.g. `"998901234567"` |

**Example request:**
```json
{
  "phone": "998901234567"
}
```

**Success response `200`:**
```json
{
  "message": "СМС код отправлен"
}
```

**DEBUG mode:** OTP code may be returned in response when SMS fails.

---

### 2.2 Customer Login — Step 2: Verify OTP → JWT

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/verify-otp/` |
| **Auth** | None (public) |

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `phone` | string | **yes** | Same phone as step 1 |
| `code` | string | **yes** | 6-digit OTP code |

**Example request:**
```json
{
  "phone": "998901234567",
  "code": "123456"
}
```

**Success response `200`:**
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
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```

**Errors:**
- `400` — invalid or expired code: `{ "detail": "Неверный код" }` / `{ "detail": "Код истёк" }`

---

### 2.3 Staff Login (Operator / Super Admin / Admin / Courier)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/admin-login/` |
| **Auth** | None (public) |

**Request body:**

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

**Success response `200`:**
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
    "created_at": "2026-01-01T08:00:00Z"
  }
}
```

**Errors:**
- `401` — `{ "detail": "Неверные данные" }`

---

### 2.4 Staff Update Own Credentials

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `/api/v1/auth/admin/update/` |
| **Auth** | JWT required |

**Request body (all optional):**

| Field | Type | Required |
|-------|------|----------|
| `phone` | string | no |
| `password` | string | no |

---

## 3. Product API — What's New

Recent changes to the **Products** model and mobile-facing APIs.

### 3.1 New / Updated Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_unit` | string enum | Price unit: `piece`, `kg`, `gram`, `liter`, `ml` |
| `unit_amount` | decimal | Base volume for price (e.g. `1` kg, `500` ml). Price formula: `(qty / unit_amount) × price` |
| `shelf_location` | string | Warehouse shelf code, e.g. `"A-32"` (for staff/picking) |
| `size_label` | string (computed) | Human-readable size in API response, e.g. `"1 kg"`, `"500 ml"` |
| `is_favourite` | boolean (computed) | `true` if product is in user's favorites (when JWT present) |
| `sale_unit` | string | Legacy internal field (`piece` / `weight`); auto-synced — **do not send from mobile** |

### 3.2 New Endpoint: Product Unit Options

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/products/unit-options/` |
| **Auth** | None (public) |

Returns metadata for each unit type — use before building cart UI.

**Response `200` (array):**
```json
[
  {
    "value": "kg",
    "label": "кг",
    "label_uz": "kg",
    "family": "weight",
    "unit_amount_default": "1",
    "unit_amount_hint": "...",
    "price_hint": "...",
    "stock_quantity_hint": "...",
    "order_quantity_hint": "...",
    "cart_units_allowed": ["kg", "gram"],
    "example": "..."
  }
]
```

### 3.3 Product List

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/products/` |
| **Auth** | Optional (JWT adds `is_favourite`) |

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | string | no | — | Search by name |
| `category` | integer | no | — | Filter by category ID |
| `is_active` | boolean | no | — | Filter active products |
| `lang` | string | no | `ru` | Translation language: `ru`, `uz`, `en` |
| `limit` | integer | no | DRF default | Pagination limit |
| `offset` | integer | no | `0` | Pagination offset |

**Response item fields:**
```json
{
  "id": 42,
  "translations": {
    "ru": { "name": "...", "description": "...", "composition": "...", "expiration_date": "...", "country": "...", "grammage": "..." },
    "uz": { ... },
    "en": { ... }
  },
  "badge": { "id": 1, "translations": {...} },
  "unit": { "id": 1, "translations": {...} },
  "shelf_location": "A-32",
  "quantity": "100.000",
  "price": "25000.00",
  "price_discount": null,
  "discount_percentage": null,
  "is_discount": false,
  "is_active": true,
  "sale_unit": "weight",
  "product_unit": "kg",
  "unit_amount": "1.000",
  "size_label": "1 kg",
  "category": { "id": 3, "translations": {...}, "children": [...] },
  "barcodes": [{ "id": 1, "barcode": "4601234567890", "is_active": true }],
  "images": [{ "id": 1, "image": "https://apies.firepole.ru/media/...", "is_active": true }],
  "is_favourite": false,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

### 3.4 Product Detail

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/products/{id}/` |
| **Auth** | Optional |

Same response shape as list item.

### 3.5 Favorites (Saved Products)

| Method | URL | Auth | Body |
|--------|-----|------|------|
| `GET` | `/api/v1/saved/` | JWT | — |
| `POST` | `/api/v1/saved/` | JWT | `{ "product_id": 42 }` |
| `DELETE` | `/api/v1/saved/{product_id}/` | JWT | — |

### 3.6 Cart Line Format (used in checkout)

When adding products to order, each line in `products_data[]`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | integer | **yes** | Product ID from `GET /products/` |
| `quantity` | decimal | **yes** | Min `0.001`. Integer for `piece`; decimal for kg/liter |
| `product_unit` | string | no | Override unit: `piece`, `kg`, `gram`, `liter`, `ml`. Default = product's `product_unit` |

**Example:**
```json
{
  "products_data": [
    { "product_id": 42, "quantity": "2", "product_unit": "piece" },
    { "product_id": 15, "quantity": "1.5", "product_unit": "kg" }
  ]
}
```

---

## 4. Order System — Full Flow by Role

### 4.1 Order Statuses

```
created → confirmed → picking → shipped → delivered → completed
                ↓         ↓         ↓
            rejected   rejected   rejected
                ↓
            cancelled (customer, only at created)
```

| Status | Meaning |
|--------|---------|
| `created` | Order placed, awaiting payment/confirmation |
| `confirmed` | Accepted by staff (card: after Click paid; cash: immediately) |
| `picking` | Warehouse picking in progress |
| `shipped` | Courier assigned, on the way |
| `delivered` | Courier at customer address |
| `completed` | **Cash only:** after courier QR confirm. Card orders finish at `delivered`+paid |
| `rejected` | Rejected by staff |
| `cancelled` | Cancelled by customer |

### 4.2 Payment Types

| Type | Flow |
|------|------|
| `card` | Create order → Click payment → auto `confirmed`+`paid` → staff processing → `delivered` deducts stock |
| `cash` | Create order → staff notified immediately → `delivered` by courier → QR confirm → `completed`+`paid` |

---

### 4.3 CUSTOMER Flow (User app)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. POST /checkout/pricing-preview/     → see total              │
│ 2. GET  /checkout/delivery-slots/      → pick time slot         │
│ 3. POST /orders/                       → create order           │
│ 4a. CARD: POST /orders/{id}/click-payment/ → open payment_url   │
│ 4b. CASH: wait for staff confirmation                           │
│ 5. Track: GET /orders/my/  or  GET /orders/{id}/                │
│ 6. Cancel (created only): POST /orders/{id}/cancel/             │
│ 7. CASH at delivery:                                            │
│    - Show QR: GET /orders/{id}/cash-qr-image/                   │
│    - After courier confirms: POST /orders/{id}/delivery-response/│
└─────────────────────────────────────────────────────────────────┘
```

#### Step-by-step

**1. Pricing preview**
```
POST /api/v1/checkout/pricing-preview/
Authorization: Bearer <token>
```
Body:
```json
{
  "products_data": [
    { "product_id": 42, "quantity": "2" }
  ],
  "delivery_date": "2026-05-20",
  "delivery_time_start": "10:00",
  "delivery_time_end": "11:00",
  "loyalty_points_to_use": 0
}
```

**2. Delivery slots**
```
GET /api/v1/checkout/delivery-slots/?relative=today
GET /api/v1/checkout/delivery-slots/?date=2026-05-20
```

**3. Create order**
```
POST /api/v1/orders/
```
Body:
```json
{
  "products_data": [
    { "product_id": 42, "quantity": "2", "product_unit": "piece" }
  ],
  "delivery_address_id": 3,
  "delivery_date": "2026-05-20",
  "delivery_time_start": "10:00",
  "delivery_time_end": "11:00",
  "payment_type": "card",
  "loyalty_points_to_use": 0,
  "leave_at_door": false,
  "comment": "Call before arrival",
  "entrance": "2",
  "apartment": "15"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `products_data` | array | **yes** | Min 1 item (see cart line format) |
| `payment_type` | string | **yes** | `card` or `cash` |
| `delivery_address_id` | integer | conditional | Saved address ID. **OR** provide `lat`+`long`+`address` |
| `lat` | decimal | conditional | Latitude |
| `long` | decimal | conditional | Longitude |
| `address` | string | conditional | Address text |
| `delivery_date` | date | optional | `YYYY-MM-DD` — all 3 delivery fields together |
| `delivery_time_start` | string | optional | `"HH:MM"` |
| `delivery_time_end` | string | optional | `"HH:MM"` |
| `loyalty_points_to_use` | integer | no | Default `0` |
| `leave_at_door` | boolean | no | Default `false` |
| `comment` | string | no | Max 5000 |
| `entrance` | string | no | Max 50 |
| `apartment` | string | no | Max 50 |

**4a. Card payment**
```
POST /api/v1/orders/{id}/click-payment/
Body: { "return_url": "safed://payment-result" }  // optional
```
Response:
```json
{
  "order_id": 8,
  "amount": "125000.00",
  "merchant_trans_id": "ORDER-8-...",
  "payment_url": "https://my.click.uz/..."
}
```

**4b. Cash:** Staff gets notification immediately. Customer waits for status updates.

**5. My orders**
```
GET /api/v1/orders/my/
GET /api/v1/orders/my/?status=shipped
```

Extra fields for cash (owner only, pending payment):
- `cash_qr_code` — token string for QR generation
- `cash_qr_image_url` — URL to `GET /orders/{id}/cash-qr-image/`

**6. Cancel order** (only `status=created`)
```
POST /api/v1/orders/{id}/cancel/
Body: {
  "reason_ids": [1, 2],
  "comment": "Changed my mind"
}
```

**7. Cash delivery — customer side**

After courier marks `delivered`, customer shows QR:
```
GET /api/v1/orders/{id}/cash-qr-image/
→ Returns PNG image
```

After courier scans QR (`courier_confirmed_cash_payment` WS event), customer confirms receipt:
```
POST /api/v1/orders/{id}/delivery-response/
Body: { "accepted": true }
```
- `accepted: true` — received order
- `accepted: false` — problem with delivery

Alternative via WebSocket (see §6.3).

#### Customer Notifications (push + WS)

| Event | `type` | When |
|-------|--------|------|
| Status change | `order_status` | confirmed, picking, shipped, etc. |
| Courier at address | `order_delivered` | status → delivered |
| Click paid | `order_click_paid` | card payment success |
| Cash confirmed | `order_cash_confirmed` | courier QR confirm |
| Courier assigned | `order_courier_assigned` | courier added |
| Picking scan | `order_picking_scan` | barcode scanned |
| Picking line update | `order_picking_line` | qty adjusted |
| Operator handling | `order_handling` | operator took order |
| Chat message | `chat_message` | new chat message |

---

### 4.4 OPERATOR / SUPER ADMIN Flow (Staff app)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GET  /orders/active/              → active orders list       │
│ 2. GET  /orders/all/                 → all orders (+ filters)   │
│ 3. GET  /orders/{id}/                → order detail             │
│ 4. PATCH /orders/{id}/status/        → change status            │
│ 5. POST  /orders/{id}/add-courier/   → assign courier           │
│ 6. PATCH /orders/{id}/picking-lines/{line_id}/ → adjust qty     │
│ 7. POST  /orders/{id}/picking/scan/  → scan barcode             │
│ 8. GET  /notifications/staff/        → staff notifications      │
└─────────────────────────────────────────────────────────────────┘
```

#### Status transitions (staff)

```
PATCH /api/v1/orders/{id}/status/
Body: { "status": "confirmed" }
```

| From | Allowed to |
|------|------------|
| `created` | `confirmed`, `rejected`, `cancelled` |
| `confirmed` | `picking`, `rejected`, `cancelled` |
| `picking` | `shipped`, `rejected`, `cancelled` |
| `shipped` | `delivered`, `rejected` |
| `delivered` | *(none via status API)* |
| `completed` | *(only via cash QR confirm — see courier)* |

**Important:** `PATCH status` with `"completed"` returns `400` — use cash QR flow.

#### Assign courier (at picking → auto shipped)

```
POST /api/v1/orders/{id}/add-courier/
Body: { "courier_id": 12 }
```

- Order must be in `picking` status
- Transitions to `shipped`
- Courier gets push (`courier_assigned`) + customer notified

#### Picking

```
PATCH /api/v1/orders/{id}/picking-lines/{line_id}/
Body: { "quantity": "1.250" }

POST /api/v1/orders/{id}/picking/scan/
Body: { "barcode": "4601234567890" }
```

`line_id` = `OrderProduct.id` (NOT `product_id`).

#### Staff Notifications

| Event | `type` | When |
|-------|--------|------|
| New cash order | `staff_new_order` | cash order created |
| New card order | `staff_new_order` | after Click paid |
| Customer cancelled | `staff_order_cancelled` | customer cancel |
| Delivery response | `staff_customer_delivery_response` | customer accept/reject after cash |

**Card orders:** Staff is NOT notified at create — only after Click payment completes.

---

### 4.5 COURIER Flow (Courier app)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GET  /orders/courier/my/          → assigned orders          │
│ 2. GET  /orders/{id}/                → order detail             │
│ 3. PATCH /orders/{id}/status/        → mark delivered           │
│ 4. PATCH /orders/cash/confirm/         → scan customer QR         │
│ 5. GET  /notifications/courier/      → courier notifications    │
└─────────────────────────────────────────────────────────────────┘
```

#### My orders
```
GET /api/v1/orders/courier/my/
GET /api/v1/orders/courier/my/?status=shipped
```

#### Mark delivered
```
PATCH /api/v1/orders/{id}/status/
Body: { "status": "delivered" }
```
- Order must be `shipped`
- Courier must be assigned to this order

#### Cash QR confirm (completes order)

```
PATCH /api/v1/orders/cash/confirm/
Body: {
  "order_id": 8,
  "qr_code": "<cash_qr_code from customer app>"
}
```

**Preconditions:**
- `payment_type = cash`
- `payment_status = pending`
- `status = delivered`
- Courier is assigned to order

**Result:**
- `payment_status` → `paid`
- `status` → `completed`
- Stock deducted
- Customer gets WS event `courier_confirmed_cash_payment`
- Customer gets push `order_cash_confirmed`

#### Courier Notifications

| Event | `type` | When |
|-------|--------|------|
| Order assigned | `courier_assigned` | POST add-courier |

**Note:** Customer delivery accept/reject does NOT notify courier (only Operator/Super Admin).

---

### 4.6 Order Response Structure

All order list/detail endpoints return:

```json
{
  "id": 8,
  "user_data": { "id": 1, "phone": "998...", "first_name": "", "last_name": "", "is_active": true },
  "comment": "...",
  "status": "shipped",
  "status_display": "Shipped",
  "can_user_cancel": false,
  "cancellation": null,
  "order_pricing": {
    "total_amount": "100000.00",
    "products_subtotal": "95000.00",
    "buffer_amount": "0.00",
    "service_fee_percent": "5.00",
    "service_fee_amount": "4750.00",
    "delivery_fee": "15000.00",
    "packing_fee": "2000.00",
    "estimated_total": "121750.00",
    "final_total": null,
    "refund_amount": "0.00",
    "payment_type": "cash",
    "payment_status": "pending",
    "loyalty_points_used": 0,
    "loyalty_discount_amount": "0.00",
    "original_estimated_total": "121750.00",
    "paid_amount": null,
    "adjustment_balance": "0.00",
    "settlement_type": "none",
    "extra_payment_due": "0.00",
    "baseline_amount": "121750.00",
    "baseline_label": "estimated"
  },
  "delivery_slot": {
    "date": "2026-05-20",
    "time_start": "10:00",
    "time_end": "11:00",
    "address": "...",
    "lat": "41.311081",
    "long": "69.240562",
    "entrance": "2",
    "apartment": "15",
    "leave_at_door": false
  },
  "order_products": [
    {
      "id": 101,
      "product_id": 42,
      "product": { /* ProductListSerializer */ },
      "ordered_quantity": "2.000",
      "quantity": "2.000",
      "product_unit": "piece",
      "normalized_quantity": "2.000",
      "unit_price": "25000.00",
      "total_price": "50000.00",
      "created_at": "..."
    }
  ],
  "order_couriers": [
    { "id": 1, "courier": { "id": 12, "phone": "...", "first_name": "...", "last_name": "..." }, "created_at": "..." }
  ],
  "cash_qr_code": null,
  "cash_qr_image_url": null,
  "created_at": "...",
  "updated_at": "..."
}
```

`cash_qr_code` / `cash_qr_image_url` only in `GET /orders/my/` for cash+pending owner.

---

## 5. Push Notifications & FCM Devices

Register device token after login to receive FCM push.

### Register / Update Device

| Method | URL | Body |
|--------|-----|------|
| `GET` | `/api/v1/devices/` | — |
| `POST` | `/api/v1/devices/` | `{ "device_token": "...", "device_type": "android" }` |
| `PUT` | `/api/v1/devices/` | `{ "device_token": "...", "device_type": "ios" }` |
| `PATCH` | `/api/v1/devices/` | `{ "device_token": "...", "is_active": false }` |

**`device_type` values:** `android`, `ios`, `web`

**POST response `201` / `200`:**
```json
{
  "id": 1,
  "device_token": "fcm_token_here",
  "device_type": "android",
  "is_active": true,
  "created_at": "...",
  "updated_at": "..."
}
```

Push is sent alongside WebSocket for order events. Always connect WS + register FCM for reliability.

---

## 6. WebSocket Protocols

Production WebSocket base: **`wss://apies.firepole.ru/`**

JWT is passed **in the URL** (not header). Use the same `access` token from login.

Run server with **Daphne** (ASGI) for WebSocket support.

---

### 6.1 Notifications WS

**URL:**
```
wss://apies.firepole.ru/ws/notifications/{access_token}/
```

**On connect — server sends unread list:**
```json
{
  "type": "unread_list",
  "items": [
    {
      "id": 55,
      "title": "Заказ в пути",
      "body": "Заказ передан курьеру...",
      "type": "order_status",
      "data": { "order_id": 8, "event": "order_status", "status": "shipped" },
      "is_read": false,
      "created_at": "2026-05-19T10:00:00+05:00"
    }
  ]
}
```

**New notification — server push:**
```json
{
  "type": "notification",
  "data": {
    "id": 56,
    "title": "...",
    "body": "...",
    "type": "staff_new_order",
    "data": { "order_id": 9 },
    "is_read": false,
    "created_at": "..."
  }
}
```

**Close codes:**
- `4001` — not authenticated (invalid/expired JWT)

---

### 6.2 Chat WS

**URL:**
```
wss://apies.firepole.ru/ws/chat/{room_id}/{access_token}/
```

**On connect — history:**
```json
{
  "type": "history",
  "messages": [ /* last 100 messages */ ]
}
```

**Send message (client → server):**
```json
{ "action": "message", "message": "Hello" }
```

**Receive message (server → client):**
```json
{
  "type": "message",
  "data": {
    "id": 10,
    "room_id": 3,
    "sender": { "id": 1, "phone": "998...", "first_name": "", "last_name": "" },
    "sender_type": "initiator",
    "message": "Hello",
    "is_read": false,
    "created_at": "..."
  }
}
```

**Mark read:**
```json
{ "action": "read" }
```

**Typing indicator:**
```json
{ "action": "typing", "is_typing": true }
```

**Other events:** `type: "read"`, `type: "typing"`

**Close codes:**
- `4001` — not authenticated
- `4003` — not allowed in this room

---

### 6.3 Cash Delivery WS

**URL (any of these):**
```
wss://apies.firepole.ru/ws/orders/delivery/{access_token}/
wss://apies.firepole.ru/ws/orders/delivery/?token={access_token}
wss://apies.firepole.ru/ws/orders/delivery/token={access_token}
```

**On connect:**
```json
{
  "type": "connected",
  "data": { "user_id": 1, "is_courier": false }
}
```

**Server → customer (after courier QR confirm):**
```json
{
  "type": "courier_confirmed_cash_payment",
  "data": {
    "order_id": 8,
    "payment_status": "paid",
    "status": "completed"
  }
}
```

**Customer accept/reject (client → server):**
```json
{ "action": "accept_delivery", "order_id": 8 }
{ "action": "reject_delivery", "order_id": 8 }
```

**Ack response:**
```json
{
  "type": "ack",
  "data": { "order_id": 8, "accepted": true, "recorded_at": "..." }
}
```

**Error:**
```json
{
  "type": "error",
  "data": { "message": "...", "code": "forbidden" }
}
```

**Important:**
- Customer delivery response notifies **Operator/Super Admin only** (via notifications WS), NOT courier
- REST alternative: `POST /orders/{id}/delivery-response/`

---

## 7. Accounts & Profile

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/users/me/` | JWT | Current user profile |
| `PUT` | `/users/me/update/` | JWT | Update `first_name`, `last_name` |
| `PUT` | `/users/me/password/send-code/` | JWT | Send OTP for password change |
| `PATCH` | `/users/me/password/` | JWT | Change password with OTP |

**Profile update body:**
```json
{ "first_name": "Ali", "last_name": "Karimov" }
```

---

## 8. Categories

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/categories/home/` | Public | Home screen categories (ordered) |
| `GET` | `/categories/` | Public | Full category tree |
| `GET` | `/categories/{id}/` | Public | Category detail |

**Query for list:** `parent`, `category`, `name`, `lang`

---

## 9. Checkout & Addresses

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `POST` | `/checkout/pricing-preview/` | JWT | Cart price preview |
| `GET` | `/checkout/delivery-slots/` | JWT | Available delivery slots |
| `GET` | `/addresses/` | JWT | Saved addresses |
| `POST` | `/addresses/` | JWT | Create address |
| `GET` | `/addresses/{id}/` | JWT | Address detail |
| `PATCH` | `/addresses/{id}/` | JWT | Update address |
| `DELETE` | `/addresses/{id}/` | JWT | Delete address |

**Delivery slots query:**

| Param | Type | Description |
|-------|------|-------------|
| `relative` | string | `today` or `tomorrow` |
| `date` | string | `YYYY-MM-DD` |

**Create address body:**
```json
{
  "lat": "41.311081",
  "long": "69.240562",
  "address": "Tashkent, Yunusabad",
  "entrance": "2",
  "apartment": "15",
  "comment": "Landmark near park"
}
```

---

## 10. Orders — All REST Endpoints

| Method | URL | Role | Description |
|--------|-----|------|-------------|
| `POST` | `/checkout/pricing-preview/` | Customer | Price preview |
| `GET` | `/checkout/delivery-slots/` | Customer | Delivery slots |
| `GET` | `/addresses/` | Customer | Addresses list |
| `POST` | `/addresses/` | Customer | Create address |
| `GET` | `/addresses/{id}/` | Customer | Address detail |
| `PATCH` | `/addresses/{id}/` | Customer | Update address |
| `DELETE` | `/addresses/{id}/` | Customer | Delete address |
| `POST` | `/orders/` | Customer | Create order |
| `GET` | `/orders/my/` | Customer | My orders |
| `GET` | `/orders/{id}/` | Customer/Staff | Order detail |
| `PUT` | `/orders/{id}/` | Customer | Update order (`created` only) |
| `DELETE` | `/orders/{id}/` | Customer | Delete order (`created` only) |
| `GET` | `/orders/cancel-reasons/` | Customer | Cancel reasons list |
| `POST` | `/orders/{id}/cancel/` | Customer | Cancel order |
| `POST` | `/orders/{id}/click-payment/` | Customer | Get Click payment URL |
| `GET` | `/orders/{id}/cash-qr-image/` | Customer | Cash QR PNG |
| `POST` | `/orders/{id}/delivery-response/` | Customer | Accept/reject delivery |
| `GET` | `/orders/all/` | Staff | All orders |
| `GET` | `/orders/active/` | Staff | Active orders |
| `PATCH` | `/orders/{id}/status/` | Staff/Courier | Change status |
| `POST` | `/orders/{id}/add-courier/` | Staff | Assign courier |
| `PATCH` | `/orders/{id}/picking-lines/{line_id}/` | Staff | Update picking line |
| `POST` | `/orders/{id}/picking/scan/` | Staff | Barcode scan |
| `GET` | `/orders/courier/my/` | Courier | Courier orders |
| `PATCH` | `/orders/cash/confirm/` | Courier | Cash QR confirm |
| `GET` | `/admin/fees/settings/` | Admin | Fee settings |
| `PATCH` | `/admin/fees/settings/` | Admin | Update fees |
| `GET` | `/admin/fees/delivery-rules/` | Admin | Delivery fee rules |
| `POST` | `/admin/fees/delivery-rules/` | Admin | Create rule |
| `PATCH` | `/admin/fees/delivery-rules/{id}/` | Admin | Update rule |
| `DELETE` | `/admin/fees/delivery-rules/{id}/` | Admin | Delete rule |
| `GET` | `/overview/` | Super Admin | Stats overview |

**Min order amount:** configurable via admin fees (default **1000 UZS** subtotal).

---

## 11. Chat (REST)

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/chat/rooms/` | JWT | My chat rooms |
| `POST` | `/chat/rooms/` | JWT | Create room `{ "order_id": 8 }` |
| `GET` | `/chat/rooms/{id}/` | JWT | Room detail + messages |
| `DELETE` | `/chat/rooms/{id}/` | JWT | Close room |
| `GET` | `/chat/orders/{order_id}/` | JWT | Room by order |
| `GET` | `/chat/rooms/{room_id}/messages/` | JWT | Message history |
| `PATCH` | `/chat/rooms/{room_id}/read/` | JWT | Mark messages read |

**Send messages via WebSocket only** (not REST POST).

---

## 12. Notifications (REST)

| Method | URL | Role | Description |
|--------|-----|------|-------------|
| `GET` | `/notifications/` | All | Auto-filter by JWT role |
| `GET` | `/notifications/customer/` | Customer | `order_*`, `chat_*` |
| `GET` | `/notifications/staff/` | Operator/SA | `staff_*`, `chat_*` |
| `GET` | `/notifications/courier/` | Courier | `courier_*` |
| `GET` | `/notifications/unread/` | All | Unread only |
| `PATCH` | `/notifications/{id}/read/` | All | Mark one read → `204` |
| `PATCH` | `/notifications/read-all/` | All | Mark all read |

**Query params (list endpoints):**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `is_read` | boolean | — | Filter read/unread |
| `type` | string | — | e.g. `staff_new_order`, `order_delivered` |
| `limit` | integer | `50` | Max `100` |
| `offset` | integer | `0` | Pagination |
| `audience` | string | auto | For `/unread/`: `customer`, `staff`, `courier` |

**Response format:**
```json
{
  "audience": "customer",
  "role": "User",
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

## 13. News

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/posts/` | Public | News feed |
| `GET` | `/posts/{id}/` | Public | Post detail |

---

## 14. Enums & Constants

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

### Language codes
`ru`, `uz`, `en` — use `?lang=uz` or `Accept-Language: uz`

---

## 15. Error Handling

Standard DRF error format:

**Validation error `400`:**
```json
{
  "field_name": ["Error message"]
}
```

**Permission `403`:**
```json
{ "detail": "Доступ запрещён" }
```

**Not found `404`:**
```json
{ "detail": "Не найден" }
```

**Business logic error `400` (with code):**
```json
{
  "detail": "Status completed faqat PATCH /orders/cash/confirm/ (QR) orqali.",
  "code": "cash_use_qr_confirm"
}
```

---

## Quick Reference — Production URLs

```
REST:  https://apies.firepole.ru/api/v1/
WS:    wss://apies.firepole.ru/ws/notifications/{JWT}/
WS:    wss://apies.firepole.ru/ws/chat/{room_id}/{JWT}/
WS:    wss://apies.firepole.ru/ws/orders/delivery/{JWT}/
Docs:  https://apies.firepole.ru/docs/
```

---

*Generated for Safed mobile team. API version: v1.*
