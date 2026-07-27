# Admin / Mobile — Sklad geolokatsiya & yetkazib berish radiusi

Frontend skladning **latitude / longitude** va **radius (km)** ni yuboradi.  
Backend validatsiya qiladi va **Haversine** formulasi bilan mijoz manzili doira ichida yoki yo‘qligini hisoblaydi.

**Base URL:** `/api/v1/`  
**Auth:** `Authorization: Bearer <access_token>`

| Rol | Endpointlar |
|-----|-------------|
| Admin / Super Admin | zona CRUD + preview |
| Mijoz (JWT) | checkout zone check |

---

## Tushuncha

```
Sklad markazi (latitude, longitude)
        +
Radius (masalan 10 km)
        =
Yetkazib berish doirasi

Mijoz GPS → Haversine masofa ≤ radius  →  allowed: true
Mijoz GPS → masofa > radius             →  allowed: false
```

DB da:
- koordinatalar: `lat`, `long`
- radius: `radius_m` (metr)

Frontend **km** yuborishi mumkin — backend metrga o‘giradi.

---

## 1. Zona yaratish (admin panel)

```http
POST /api/v1/admin/delivery-zones/
Content-Type: application/json
```

### Tavsiya etilgan body (frontend)

```json
{
  "name": "Asosiy sklad",
  "address": "Toshkent, Chilonzor",
  "latitude": 41.311081,
  "longitude": 69.240562,
  "radius_km": 10,
  "is_active": true
}
```

### Legacy aliaslar (ham ishlaydi)

```json
{
  "name": "Asosiy sklad",
  "lat": 41.311081,
  "long": 69.240562,
  "radius_m": 10000
}
```

| Maydon | Majburiy | Validatsiya |
|--------|----------|-------------|
| `latitude` yoki `lat` | ✅ | −90 … 90 |
| `longitude` yoki `long` | ✅ | −180 … 180 |
| `radius_km` yoki `radius_m` | ✅ | km: 0.001…500; m: ≥ 1 |
| `name` | ❌ | |
| `address` | ❌ | bo‘sh bo‘lsa `name` yoki `"Склад"` |
| `is_active` | ❌ | default `true` |

### Response `201`

```json
{
  "id": 1,
  "name": "Asosiy sklad",
  "address": "Toshkent, Chilonzor",
  "lat": "41.311081000000000000",
  "long": "69.240562000000000000",
  "radius_m": 10000,
  "radius_km_display": 10.0,
  "is_active": true,
  "created_at": "2026-07-27T16:00:00Z",
  "updated_at": "2026-07-27T16:00:00Z"
}
```

`radius_km: 10` → ichki `radius_m: 10000`.

---

## 2. Zonalar ro‘yxati / tahrir / o‘chirish

| Method | Path | Izoh |
|--------|------|------|
| `GET` | `/admin/delivery-zones/` | Barcha zonalar |
| `PATCH` | `/admin/delivery-zones/{id}/` | Qisman yangilash (shu maydonlar) |
| `DELETE` | `/admin/delivery-zones/{id}/` | O‘chirish |

**PATCH misol** — faqat radiusni o‘zgartirish:

```json
{
  "radius_km": 15
}
```

---

## 3. Preview — saqlamasdan sinash (admin)

Xarita / slider da radiusni o‘zgartirganda, DB ga yozmasdan mijoz nuqtasini tekshirish.

```http
POST /api/v1/admin/delivery-zones/preview/
Content-Type: application/json
```

```json
{
  "warehouse_latitude": 41.311081,
  "warehouse_longitude": 69.240562,
  "radius_km": 10,
  "customer_latitude": 41.312,
  "customer_longitude": 69.241
}
```

### Response `200`

```json
{
  "allowed": true,
  "message": "",
  "matched_zone_id": null,
  "nearest_zone_id": null,
  "distance_m": 120.5,
  "distance_km": 0.121
}
```

| Maydon | Ma’nosi |
|--------|---------|
| `allowed` | `true` — mijoz radius ichida |
| `distance_m` / `distance_km` | sklad → mijoz Haversine masofa |
| `message` | `allowed=false` bo‘lsa izoh |

---

## 4. Mijoz: checkout oldidan tekshiruv

```http
GET /api/v1/checkout/delivery-zone/check/?latitude=41.312&longitude=69.241
```

Aliaslar: `lat` / `long` ham ishlaydi.

```http
GET /api/v1/checkout/delivery-zone/check/?lat=41.312&long=69.241
```

### Response `200`

```json
{
  "allowed": true,
  "message": "",
  "matched_zone_id": 1,
  "nearest_zone_id": 1,
  "distance_m": 120.5,
  "distance_km": 0.121
}
```

| Holat | Natija |
|-------|--------|
| Faol zona yo‘q | `allowed: true` (cheklov yo‘q) |
| Kamida bitta zona ichida | `allowed: true`, `matched_zone_id` |
| Hech birida emas | `allowed: false` + eng yaqin zona masofasi |

Buyurtma yaratishda ham shu tekshiruv ishlaydi — zona tashqarisida `400` + `outside_delivery_zone`.

---

## 5. Frontend flow (tavsiya)

### Admin panel

```
1. Xaritada sklad pin → latitude, longitude
2. Radius slider (km) → radius_km
3. (ixtiyoriy) Preview:
   POST /admin/delivery-zones/preview/
4. Saqlash:
   POST /admin/delivery-zones/
5. Ro‘yxat:
   GET /admin/delivery-zones/
```

### Mobil ilova (mijoz)

```
1. Manzil / GPS olindi
2. GET /checkout/delivery-zone/check/?latitude=&longitude=
3. allowed=false → UI: «Yetkazib berish zonasi tashqarisida»
4. allowed=true  → checkout davom etadi
```

---

## 6. Validatsiya xatolari (misol)

Noto‘g‘ri kenglik:

```json
{
  "latitude": ["latitude must be between -90 and 90"]
}
```

Radius / koordinata yo‘q:

```json
{
  "latitude": ["Обязательное поле (latitude yoki lat)."],
  "longitude": ["Обязательное поле (longitude yoki long)."],
  "radius_km": ["Обязательное поле (radius_km yoki radius_m)."]
}
```

---

## 7. Tezkor endpoint jadvali

| Method | Path | Kim |
|--------|------|-----|
| GET | `/admin/delivery-zones/` | Admin |
| POST | `/admin/delivery-zones/` | Admin |
| PATCH | `/admin/delivery-zones/{id}/` | Admin |
| DELETE | `/admin/delivery-zones/{id}/` | Admin |
| POST | `/admin/delivery-zones/preview/` | Admin |
| GET | `/checkout/delivery-zone/check/` | Mijoz |

---

## 8. Texnik eslatmalar

1. Masofa: **Haversine** (WGS84, Yer radiusi 6371 km).
2. Frontend `radius_km` yuboradi → backend `radius_m = round(km × 1000)` saqlaydi.
3. Bir nechta faol zona bo‘lsa — **birortasiga** tushsa yetarli.
4. Preview DB ga yozmaydi; CRUD yozadi.
5. Kod: `apps/core/geo.py`, `apps/orders/services/delivery_zone.py`, `DeliveryZoneSerializer`.
