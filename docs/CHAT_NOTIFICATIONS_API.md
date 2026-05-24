# Safed — Chat & Notifications API (Mobile)

Production-ready reference for **chat** and **push/in-app notifications** (REST + WebSocket).

---

## Table of Contents

1. [General Info](#1-general-info)
2. [Authentication (JWT)](#2-authentication-jwt)
3. [WebSocket URLs (Quick Reference)](#3-websocket-urls-quick-reference)
4. [Notifications — REST](#4-notifications--rest)
5. [Notifications — WebSocket](#5-notifications--websocket)
6. [Chat — REST](#6-chat--rest)
7. [Chat — WebSocket](#7-chat--websocket)
8. [Notification Types by Role](#8-notification-types-by-role)
9. [Mobile Integration Flow](#9-mobile-integration-flow)
10. [Error Handling](#10-error-handling)

---

## 1. General Info

| Field | Value |
|-------|-------|
| **Project** | Safed |
| **Framework** | Django + Django REST Framework + Django Channels |
| **API version** | `v1` |
| **REST base (prod)** | `https://apies.firepole.ru/api/v1/` |
| **WebSocket base (prod)** | `wss://apies.firepole.ru/` |
| **REST base (local)** | `http://127.0.0.1:8000/api/v1/` |
| **WebSocket base (local)** | `ws://127.0.0.1:8000/` |
| **Content-Type (REST)** | `application/json` |
| **Auth (REST)** | `Authorization: Bearer <access_token>` |
| **Auth (WebSocket)** | JWT **in URL path** (see below) |

> WebSocket server **Daphne** (ASGI) bilan ishlaydi. Faqat HTTP (Gunicorn) bo‘lsa WS ulanmaydi.

---

## 2. Authentication (JWT)

### 2.1 Customer — Send OTP

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/login/` |
| **Auth** | None |

**Body:**

| Field | Type | Required |
|-------|------|----------|
| `phone` | string | **yes** |

```json
{ "phone": "998901234567" }
```

---

### 2.2 Customer — Verify OTP → JWT

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/verify-otp/` |
| **Auth** | None |

**Body:**

| Field | Type | Required |
|-------|------|----------|
| `phone` | string | **yes** |
| `code` | string | **yes** |

```json
{
  "phone": "998901234567",
  "code": "123456"
}
```

**Response `200`:**

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

---

### 2.3 Staff (Operator / Courier / Admin) — Login

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/auth/admin-login/` |
| **Auth** | None |

**Body:**

| Field | Type | Required |
|-------|------|----------|
| `phone` | string | **yes** |
| `password` | string | **yes** |

```json
{
  "phone": "998901111111",
  "password": "mypassword123"
}
```

**Response `200`:** same shape as OTP (`access`, `refresh`, `user`).

---

### 2.4 REST header (barcha GET/PATCH/POST)

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: application/json
```

### 2.5 WebSocket JWT

WebSocket da **header emas**, URL ichida `access` token:

```
wss://apies.firepole.ru/ws/notifications/{ACCESS_TOKEN}/
wss://apies.firepole.ru/ws/chat/{ROOM_ID}/{ACCESS_TOKEN}/
```

Alternativa (Postman): header `Authorization: Bearer {ACCESS_TOKEN}` ham qabul qilinadi.

---

## 3. WebSocket URLs (Quick Reference)

| Maqsad | Production URL | Qachon ulash |
|--------|----------------|--------------|
| **Notifications (real-time)** | `wss://apies.firepole.ru/ws/notifications/{JWT}/` | Login dan keyin, ilova ochiq bo‘lganda |
| **Chat (xabar yuborish/qabul)** | `wss://apies.firepole.ru/ws/chat/{room_id}/{JWT}/` | Chat ekrani ochilganda |
| Delivery events (buyurtma) | `wss://apies.firepole.ru/ws/orders/delivery/{JWT}/` | Cash/card QR completion (alohida hujjat) |

**`{JWT}`** = login javobidagi `access` string (URL-encode kerak bo‘lishi mumkin).

**Close codes:**

| Code | Ma’nosi |
|------|---------|
| `4001` | JWT noto‘g‘ri yoki muddati tugagan |
| `4003` | Chat: bu room ga kirish huquqi yo‘q |

---

## 4. Notifications — REST

Bildirishnomalar **avtomatik yaratiladi** (order status, chat, staff event).  
Mobil ilova **GET** bilan tarix oladi, **WS** bilan real-time yangilanadi.

### 4.1 List (avto — JWT rol bo‘yicha)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/notifications/` |
| **Auth** | JWT **required** |

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `is_read` | boolean | no | — | `true` / `false` |
| `type` | string | no | — | Masalan `order_status`, `staff_new_order` |
| `limit` | integer | no | `50` | Max `100` |
| `offset` | integer | no | `0` | Pagination |

**Response `200`:**

```json
{
  "audience": "customer",
  "role": "User",
  "unread_count": 3,
  "count": 25,
  "limit": 50,
  "offset": 0,
  "results": [
    {
      "id": 55,
      "title": "Заказ в пути",
      "body": "Заказ передан курьеру и уже в пути к вам.",
      "type": "order_status",
      "data": {
        "order_id": 8,
        "event": "order_status",
        "status": "shipped"
      },
      "is_read": false,
      "created_at": "2026-05-23T10:00:00Z"
    }
  ]
}
```

---

### 4.2 List — Mijoz (customer)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/notifications/customer/` |
| **Auth** | JWT (User) |

Faqat `order_*` va `chat_*` turlar.

---

### 4.3 List — Operator / Super Admin

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/notifications/staff/` |
| **Auth** | JWT (Operator yoki Super Admin) |

Faqat `staff_*` va `chat_*`. Boshqa rol → `403`.

---

### 4.4 List — Kuryer

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/notifications/courier/` |
| **Auth** | JWT (Courier) |

Faqat `courier_*`. Boshqa rol → `403`.

---

### 4.5 Faqat o‘qilmaganlar

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/notifications/unread/` |
| **Auth** | JWT |

**Query:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `audience` | string | no | `customer` \| `staff` \| `courier` (default: JWT rol) |

---

### 4.6 Bitta bildirishnomani o‘qilgan deb belgilash

| | |
|---|---|
| **Method** | `PATCH` |
| **URL** | `/api/v1/notifications/{id}/read/` |
| **Auth** | JWT |
| **Body** | bo‘sh |

**Response:** `204 No Content`

**Errors:** `404` — topilmadi yoki boshqa user ga tegishli.

---

### 4.7 Hammasini o‘qilgan deb belgilash

| | |
|---|---|
| **Method** | `PATCH` |
| **URL** | `/api/v1/notifications/read-all/` |
| **Auth** | JWT |
| **Body** | bo‘sh |

**Response `200`:**

```json
{ "marked_read": 12 }
```

---

### 4.8 Notification yaratish (REST emas)

| Manba | Qachon |
|-------|--------|
| Order hooks | status o‘zgarishi, yangi buyurtma, kuryer, picking, … |
| Chat WS | yangi xabar yuborilganda qabul qiluvchiga `chat_message` |
| FCM push | `POST /api/v1/devices/` da token bo‘lsa |

Mobil ilova notification **POST qilmaydi** — faqat GET + WS qabul qiladi.

---

## 5. Notifications — WebSocket

### 5.1 URL

**Production:**
```
wss://apies.firepole.ru/ws/notifications/eyJ0eXAiOiJKV1QiLCJhbGc.../
```

**Local:**
```
ws://127.0.0.1:8000/ws/notifications/eyJ0eXAiOiJKV1QiLCJhbGc.../
```

### 5.2 Ulanish (React Native / Flutter pseudocode)

```javascript
const access = await getStoredAccessToken();
const ws = new WebSocket(
  `wss://apies.firepole.ru/ws/notifications/${access}/`
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'unread_list') {
    // connect bo‘lganda: oxirgi 20 ta o‘qilmagan
    setUnread(msg.items);
  }
  if (msg.type === 'notification') {
    // yangi bildirishnoma
    addNotification(msg.data);
  }
};
```

### 5.3 Server → Client messages

#### A) Connect — unread list

```json
{
  "type": "unread_list",
  "items": [
    {
      "id": 55,
      "title": "Новое сообщение",
      "body": "Salom",
      "type": "chat_message",
      "data": {
        "room_id": 3,
        "order_id": 8,
        "sender_id": 2,
        "message_id": 10
      },
      "is_read": false,
      "created_at": "2026-05-23T10:00:00+05:00"
    }
  ]
}
```

#### B) Yangi bildirishnoma (real-time)

```json
{
  "type": "notification",
  "data": {
    "id": 56,
    "title": "Новый заказ",
    "body": "Заказ №9 на сумму 125000.00 сум",
    "type": "staff_new_order",
    "data": { "order_id": 9, "event": "staff_new_order" },
    "is_read": false,
    "created_at": "2026-05-23T10:05:00+05:00"
  }
}
```

### 5.4 Client → Server

Notification WS **faqat qabul qiladi** — client dan xabar yuborish shart emas.

O‘qilgan deb belgilash REST orqali: `PATCH /notifications/{id}/read/`.

---

## 6. Chat — REST

Har bir **buyurtma** uchun **bitta chat room** (`order` ↔ `ChatRoom` OneToOne).

### 6.1 Chat yaratish (POST)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/v1/chat/rooms/` |
| **Auth** | JWT **required** |

**Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `order_id` | integer | **yes** | Buyurtma ID (`Order.id`) |

```json
{ "order_id": 8 }
```

**Response `201`** (yangi room) yoki **`200`** (allaqachon bor):

```json
{
  "id": 3,
  "order": 8,
  "initiator": {
    "id": 1,
    "phone": "998901234567",
    "groups": ["User"],
    "first_name": "",
    "last_name": "",
    "full_name": "998901234567"
  },
  "receiver": {
    "id": 5,
    "phone": "998901111111",
    "groups": ["Operator"],
    "first_name": "Ali",
    "last_name": "",
    "full_name": "Ali"
  },
  "is_active": true,
  "last_message": null,
  "unread_count": 0,
  "created_at": "2026-05-23T09:00:00Z",
  "updated_at": "2026-05-23T09:00:00Z",
  "messages": []
}
```

**Qoidalar:**
- `initiator` = chat ochgan user (odatda mijoz)
- `receiver` = tasodifiy aktiv **Operator** (bo‘lsa)
- Bir `order_id` uchun ikkinchi marta POST → mavjud room qaytadi (`200`)

---

### 6.2 Mening chatlarim (GET list)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/chat/rooms/` |
| **Auth** | JWT |

| Kim | Ko‘radi |
|-----|---------|
| **Mijoz** | `initiator = men` |
| **Staff** | `receiver = men` |

**Response `200`:** `ChatRoomSerializer[]` (messages yo‘q, faqat `last_message` preview).

---

### 6.3 Chat detail + barcha xabarlar (GET)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/chat/rooms/{id}/` |
| **Auth** | JWT |

**Response:** yuqoridagi kabi + `messages[]`.  
Kirishda **boshqaning** o‘qilmagan xabarlari `is_read=true` qilinadi.

---

### 6.4 Chat buyurtma bo‘yicha (GET)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/chat/orders/{order_id}/` |
| **Auth** | JWT |

Buyurtma egasi yoki staff. Chat yo‘q → `404`.

---

### 6.5 Xabarlar tarixi (GET)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/chat/rooms/{room_id}/messages/` |
| **Auth** | JWT |

**Response `200`:**

```json
[
  {
    "id": 10,
    "room": 3,
    "sender": {
      "id": 1,
      "phone": "998901234567",
      "groups": ["User"],
      "first_name": "",
      "last_name": "",
      "full_name": "998901234567"
    },
    "sender_type": "initiator",
    "message": "Salom, buyurtma qachon keladi?",
    "is_read": true,
    "created_at": "2026-05-23T09:30:00Z"
  }
]
```

| Field | Description |
|-------|-------------|
| `sender_type` | `"initiator"` = **men** yuborgan (o‘ng tomonda UI) |
| `sender_type` | `"receiver"` = **boshqa** yuborgan (chap tomonda UI) |

> **Xabar yuborish REST da yo‘q** — faqat WebSocket.

---

### 6.6 Xabarlarni o‘qilgan deb belgilash (REST)

| | |
|---|---|
| **Method** | `PATCH` |
| **URL** | `/api/v1/chat/rooms/{room_id}/read/` |
| **Auth** | JWT |

**Response `200`:**

```json
{ "marked_read": 4 }
```

---

### 6.7 Chatni yopish

| | |
|---|---|
| **Method** | `DELETE` |
| **URL** | `/api/v1/chat/rooms/{id}/` |
| **Auth** | JWT |

Soft delete: `is_active=false`. Response: `204`.

---

## 7. Chat — WebSocket

### 7.1 URL

**Production:**
```
wss://apies.firepole.ru/ws/chat/{room_id}/{JWT}/
```

**Misol:**
```
wss://apies.firepole.ru/ws/chat/3/eyJ0eXAiOiJKV1QiLCJhbGc.../
```

`room_id` = `POST /chat/rooms/` yoki `GET /chat/rooms/` dan `id`.

### 7.2 Ulanish flow

```
1. POST /chat/rooms/  { order_id: 8 }  → room.id = 3
2. WS connect: wss://.../ws/chat/3/{access}/
3. Server yuboradi: { type: "history", messages: [...] }
4. Client yuboradi xabarlar (action: message)
5. Qabul qiluvchiga parallel: WS notification (type: chat_message)
```

### 7.3 Server → Client

#### Connect — history (oxirgi 100 ta)

```json
{
  "type": "history",
  "messages": [
    {
      "id": 10,
      "sender": {
        "id": 1,
        "phone": "998901234567",
        "first_name": "",
        "last_name": ""
      },
      "sender_type": "initiator",
      "message": "Salom",
      "is_read": false,
      "created_at": "2026-05-23T09:30:00Z"
    }
  ]
}
```

#### Yangi xabar

```json
{
  "type": "message",
  "data": {
    "id": 11,
    "room_id": 3,
    "sender": {
      "id": 5,
      "phone": "998901111111",
      "first_name": "Ali",
      "last_name": ""
    },
    "sender_type": "receiver",
    "message": "Tez orada yetkazamiz",
    "is_read": false,
    "created_at": "2026-05-23T09:31:00Z"
  }
}
```

#### O‘qildi (kimdir read bosganda)

```json
{
  "type": "read",
  "data": { "user_id": 1, "count": 2 }
}
```

#### Yozmoqda (typing)

```json
{
  "type": "typing",
  "data": { "user_id": 5, "is_typing": true }
}
```

### 7.4 Client → Server

#### Xabar yuborish

```json
{
  "action": "message",
  "message": "Salom, qachon keladi?"
}
```

| Field | Type | Required |
|-------|------|----------|
| `action` | string | **yes** | `"message"` |
| `message` | string | **yes** | 1–5000 belgi |

Natija: DB ga saqlanadi, room dagi barcha ulangan clientlarga `type: message`, qabul qiluvchiga **notification WS** + **FCM** (agar device token bor).

#### O‘qilgan deb belgilash

```json
{ "action": "read" }
```

#### Typing indicator

```json
{ "action": "typing", "is_typing": true }
```

---

## 8. Notification Types by Role

| Rol | `type` | Qachon |
|-----|--------|--------|
| **Mijoz** | `order_status` | Status o‘zgarishi |
| **Mijoz** | `order_delivered` | Kuryer manzilda |
| **Mijoz** | `order_click_paid` | Click to‘lov |
| **Mijoz** | `order_cash_confirmed` | Cash QR tasdiq |
| **Mijoz** | `order_courier_assigned` | Kuryer biriktirildi |
| **Mijoz** | `order_picking_scan` | Skaner |
| **Mijoz** | `order_picking_line` | Miqdor yangilandi |
| **Mijoz** | `order_handling` | Operator qabul qildi |
| **Mijoz** | `chat_message` | Yangi chat xabari |
| **Operator / SA** | `staff_new_order` | Yangi buyurtma |
| **Operator / SA** | `staff_order_cancelled` | Mijoz bekor qildi |
| **Operator / SA** | `staff_customer_delivery_response` | Mijoz oldim/rad |
| **Operator / SA** | `chat_message` | Yangi chat xabari |
| **Kuryer** | `courier_assigned` | Buyurtma biriktirildi |

---

## 9. Mobile Integration Flow

### 9.1 Ilova ochilganda (har bir rol)

```
1. Login → access token saqlash
2. POST /devices/  { device_token, device_type: "android"|"ios" }  → FCM
3. WS ulanish: wss://apies.firepole.ru/ws/notifications/{access}/
4. GET /notifications/unread/  → inbox UI
```

### 9.2 Mijoz — buyurtma chat

```
1. POST /chat/rooms/  { "order_id": 8 }
2. room_id olish (masalan 3)
3. WS: wss://apies.firepole.ru/ws/chat/3/{access}/
4. Tarix: GET /chat/rooms/3/messages/  (ixtiyoriy, WS history ham bor)
5. Yuborish: WS { "action": "message", "message": "..." }
```

### 9.3 Operator — chat ro‘yxati

```
1. GET /chat/rooms/  → mijozlar bilan chatlar
2. Tanlangan room → WS /ws/chat/{id}/{access}/
3. GET /notifications/staff/  yoki WS notifications
```

### 9.4 Qaysi URL qachon?

| Vazifa | REST | WebSocket |
|--------|------|-----------|
| Chat ochish | `POST /chat/rooms/` | — |
| Chat ro‘yxati | `GET /chat/rooms/` | — |
| Xabar tarixi | `GET /chat/rooms/{id}/messages/` | connect da `history` |
| Xabar yuborish | ❌ | `WS chat` `action: message` |
| Bildirishnoma tarixi | `GET /notifications/` | connect da `unread_list` |
| Yangi bildirishnoma | — | `WS notifications` `type: notification` |
| O‘qilgan deb belgilash | `PATCH /notifications/{id}/read/` | — |

---

## 10. Error Handling

### REST

| HTTP | Body |
|------|------|
| `401` | JWT yo‘q / noto‘g‘ri |
| `403` | Rol yetarli emas (masalan `/notifications/staff/`) |
| `404` | Chat / notification topilmadi |

```json
{ "detail": "Чат не найден" }
```

### WebSocket

| Code | Sabab |
|------|-------|
| `4001` | Token invalid — qayta login |
| `4003` | Chat room ga ruxsat yo‘q |

---

## Quick Copy — Production URLs

```
REST notifications:  GET  https://apies.firepole.ru/api/v1/notifications/
REST chat create:    POST https://apies.firepole.ru/api/v1/chat/rooms/
REST chat list:      GET  https://apies.firepole.ru/api/v1/chat/rooms/

WS notifications:    wss://apies.firepole.ru/ws/notifications/{ACCESS_TOKEN}/
WS chat:             wss://apies.firepole.ru/ws/chat/{ROOM_ID}/{ACCESS_TOKEN}/
```

---

*Safed mobile team — Chat & Notifications v1*
