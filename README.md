# Safed — Mobile Backend

Django asosidagi e-commerce mobil backend loyihasi.

---

## Texnologiyalar

| Texnologiya | Maqsad |
|-------------|--------|
| **Django 6** | Backend framework |
| **Django REST Framework** | REST API |
| **PostgreSQL** | Ma'lumotlar bazasi |
| **Elasticsearch 9** | Qidiruv va indekslash |
| **django-parler** | Ko'p tillilik (uz, ru, en) |
| **django-elasticsearch-dsl** | Elasticsearch bilan integratsiya |
| **drf-spectacular** | Swagger/OpenAPI hujjatlari |
| **django-cors-headers** | CORS qoidalari |
| **django-filter** | Qidiruv va filtrlash |
| **JWT (SimpleJWT)** | Autentifikatsiya |
| **Pillow** | Rasm qayta ishlash |

---

## Loyihani ishga tushirish

### 1. O'rnatish

```bash
# Virtual muhit yaratish
python -m venv env

# Virtual muhitni faollashtirish (Windows)
env\Scripts\activate

# Paketlarni o'rnatish
pip install -r requirements.txt
```

### 2. Environment (.env)

Loyiha ildizida `.env` faylini yarating:

```env
DB_NAME=safed
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### 3. Ma'lumotlar bazasi

PostgreSQL'da `safed` database yarating va migrationlarni bajaring:

```bash
python manage.py migrate
```

### 4. Serverni ishga tushirish (Daphne + ASGI)

```bash
# Development
daphne -b 0.0.0.0 -p 9000 config.asgi:application
```

Server: `http://127.0.0.1:9000` (HTTP va WebSocket birgalikda)

---

## Elasticsearch

### O'rnatish (Windows, Dockersiz)

1. [Elasticsearch](https://www.elastic.co/downloads/elasticsearch) ni yuklab oling (Windows x64 .zip)
2. Zipni oching va `bin\elasticsearch.bat` ni ishga tushiring
3. Rivojlantirish uchun xavfsizlikni o'chirish: `config\elasticsearch.yml` oxiriga qo'shing:
   ```yaml
   xpack.security.enabled: false
   ```
4. Qayta ishga tushiring

### Tekshirish

Brauzerda: `http://localhost:9200` — JSON javob kelishi kerak.

### Django bilan ishlatish

Sozlamalar (`config/settings.py`):

```python
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': ['http://localhost:9200'],
    },
}
ELASTICSEARCH_DSL_AUTOSYNC = True
ELASTICSEARCH_DSL_AUTO_REFRESH = True
```

### Foydali buyruqlar

```bash
# Indexlarni qayta yaratish
python manage.py search_index --rebuild

# Indexlarni yangilash
python manage.py search_index --populate
```

### Document qo'shish

Har bir app da `documents.py` faylida Document yoziladi (masalan: `apps/categories/documents.py`). Model o'zgarganda ELASTICSEARCH_DSL_AUTOSYNC orqali indeks avtomatik yangilanadi.

---

## Foydali buyruqlar

```bash
# Fake kategoriyalar yaratish
python manage.py create_fake_categories

# Default admin yaratish (phone=123456789, password=123456789admin@#)
python manage.py create_admin

# Superuser yaratish
python manage.py createsuperuser
```

---

## Loyiha strukturasi

```
Safed/
├── config/           # Asosiy sozlamalar
│   ├── settings.py
│   ├── urls.py
│   └── spectacular/
├── apps/
│   ├── accounts/      # Foydalanuvchilar, rollar, OTP, devices
│   ├── categories/    # Kategoriyalar (parent/child, icon, translations)
│   ├── news/          # Yangiliklar (multilang, images, Elasticsearch)
│   ├── orders/        # Zakazlar (Order, OrderProduct, OrderCourier)
│   ├── products/      # Mahsulotlar
│   └── realtime/      # Chat va notificatsiyalar (WebSocket + REST)
├── manage.py
├── requirements.txt
└── .env
```

---

## Swagger

- **Swagger UI:** `http://127.0.0.1:9000/docs/`
- **ReDoc:** `http://127.0.0.1:9000/redoc/`

---

## Rollar va ularning imkoniyatlari

Loyihada quyidagi rollar ishlatiladi (Django `Group` larida):

- **User** – oddiy mijoz, mobil ilova foydalanuvchisi.
- **Super Admin** – yuqori darajadagi admin (boshqaruv).
- **Admin** – mahsulot va zakazlar bilan ishlovchi admin.
- **Operator** – chat va foydalanuvchilar bilan ishlovchi operator.
- **Dostavchik** (Courier) – buyurtmalarni yetkazib beruvchi.

### User

- **Auth & profil**
  - `POST /api/auth/send-otp/` – telefon raqamiga SMS kod yuborish.
  - `POST /api/auth/verify-otp/` – kodni tasdiqlash, JWT olish.
  - `GET /api/users/me/` – o‘z profilini olish.
  - `PUT /api/users/me/update/` – `first_name`, `last_name` yangilash.
  - `POST /api/users/me/password/send-code/` – parolni o‘zgartirish uchun SMS kod.
  - `PATCH /api/users/me/password/` – kod bilan parolni o‘zgartirish.

- **Products & categories & news (hamma uchun ochiq, lekin ko‘proq User ishlatadi)**
  - `GET /api/products/` – mahsulotlar ro‘yxati (pagination).
  - `GET /api/categories/` – kategoriyalar daraxti.
  - `GET /api/news/` va `GET /api/news/{id}/` – yangiliklar.

- **Orders**
  - `POST /api/orders/` – yangi zakaz yaratish (`products_data`, `lat`, `long`, `address`, status = `pending`).
  - `GET /api/my-orders/` – o‘z zakazlari ro‘yxati (status bo‘yicha filtrlash).
  - `GET /api/orders/{id}/` – o‘z zakazini ko‘rish.

- **Chat**
  - `GET /api/orders/{order_id}/chat/` – o‘z zakazi bo‘yicha chat tarixini ko‘rish.
  - `POST /api/orders/{order_id}/chat/` – chatga xabar yozish.
  - `ws://localhost/ws/chat/{order_id}/{access_token}/` – real-time chat.

- **Notifications**
  - `GET /api/notifications/` – barcha notificatsiyalar.
  - `GET /api/notifications/unread/` – faqat o‘qilmaganlari.
  - `PATCH /api/notifications/{id}/read/` – bitta notificatsiyani o‘qilgan qilish.
  - `ws://localhost/ws/notification/{access_token}/` – faqat shu User uchun real-time notificatsiyalar (faqat o‘qilmaganlari keladi).

### Super Admin

Super Admin – barcha Admin/Operator/Dostavchiklarni yaratish va boshqarish huquqiga ega, shuningdek barcha zakazlar va mahsulotlar bilan ishlay oladi.

- **Staff boshqaruvi**
  - `POST /api/staff/create/` – Admin / Operator / Courier (Dostavchik) yaratish. +
  - `GET /api/users/group/users/` – User lar ro‘yxati. Filter: `first_name`, `last_name`, `phone`. Pagination: `limit`, `offset`. +
  - `GET /api/staff/admins/` – Admin lar ro‘yxati. Filter: `first_name`, `last_name`, `phone`. Pagination: `limit`, `offset`. +
  - `GET /api/staff/operators/` – Operatorlar ro‘yxati. Filter: `first_name`, `last_name`, `phone`. Pagination: `limit`, `offset`. +
  - `GET /api/staff/couriers/` – Dostavchiklar ro‘yxati (`is_busy` maydoni bilan). Filter: `first_name`, `last_name`, `phone`. + Pagination: `limit`, `offset`.
  - `GET /api/users/{id}/` – foydalanuvchini ko‘rish. +
  - `PUT /api/users/{id}/` – foydalanuvchini yangilash. +
  - `DELETE /api/users/{id}/` – foydalanuvchini o‘chirish. +
  - `PATCH /api/users/{id}/password/` – istalgan foydalanuvchi parolini o‘zgartirish. +

- **Mahsulot va kategoriyalar**
  - Products app’dagi barcha CRUD endpointlar.
  - Categories:
    - `GET /api/categories/` – daraxt ko‘rinishida ro‘yxat. +
    - `POST /api/categories/` – root kategoriya yaratish (FormData + icon). +
    - `POST /api/categories/child/` – child kategoriya yaratish. +
    - `GET/PUT/DELETE /api/categories/{id}/` – kategoriya bilan ishlash. +

- **Orders**
  - `GET /api/orders/` – barcha zakazlar (status va user bo‘yicha filtrlash).
  - `GET /api/orders/{id}/` – istalgan zakazni ko‘rish.
  - `PUT /api/orders/{id}/` – `pending` holatdagi zakazni yangilash.
  - `DELETE /api/orders/{id}/` – `pending` holatdagi zakazni o‘chirish.
  - `PATCH /api/orders/{id}/status/` – statusni o‘zgartirish (`pending`, `process`, `delivering`, `completed`, `rejected`).
  - `POST /api/orders/{id}/add-courier/` – zakazga Dostavchik biriktirish (status `delivering` ga o‘tadi).

- **Statistika**
  - `GET /api/stats/overview/` – umumiy statistika (faqat Super Admin):
    - query paramlar: `date_from`, `date_to`, `period` (`daily`, `weekly`, `monthly`);
    - jami zakazlar soni;
    - jami mijozlar soni;
    - `completed` zakazlar bo‘yicha umumiy tushum;
    - statuslar bo‘yicha taqsimot (pending/process/delivering/completed/rejected);
    - `orders_timeseries` va `revenue_timeseries` – grafiklar uchun vaqt bo‘yicha massiv (kunlik/haftalik/oylik).
  - `GET /api/stats/products/` – mahsulotlar statistikasi (faqat Super Admin):
    - query paramlar: `date_from`, `date_to`, `category` (kategoriya ID), `period` (`daily`, `weekly`, `monthly`);
    - eng ko‘p sotilgan mahsulotlar (miqdor va tushum bo‘yicha);
    - ombordagi umumiy quantity;
    - `quantity <= 5` bo‘lgan “kam qolgan” mahsulotlar ro‘yxati;
    - `sales_timeseries` – vaqt bo‘yicha sotuvlar (miqdor va tushum) grafiklar uchun.

### Admin

Admin – asosan mahsulotlar va zakazlar bilan ishlaydi.

- **Mahsulotlar**
  - Products app’dagi CRUD endpointlar (yaratish, yangilash, o‘chirish).

- **Orders**
  - `GET /api/orders/` – barcha zakazlarni ko‘rish.
  - `GET /api/orders/{id}/` – zakaz detali.
  - `PUT /api/orders/{id}/` – `pending` holatdagi zakazni yangilash (masalan, product ro‘yxati, address).
  - `DELETE /api/orders/{id}/` – `pending` holatdagi zakazni o‘chirish.
  - `PATCH /api/orders/{id}/status/` – statuslarni boshqarish:
    - `pending` → `process` → `delivering` → `completed` yoki `rejected`.
  - `POST /api/orders/{id}/add-courier/` – zakazga Dostavchik tayinlash (status avtomatik `delivering` bo‘ladi).

### Operator

Operator – chat va foydalanuvchilar bilan ishlaydi.

- **Foydalanuvchilar**
  - `GET /api/users/group/user/` – User lar ro‘yxati (filtrlash: `first_name`, `last_name`, `phone`).
  - `GET /api/users/{id}/` – foydalanuvchini ko‘rish.

- **Orders**
  - `GET /api/orders/` va `GET /api/orders/{id}/` – barcha zakazlarni ko‘rish (faqat o‘qish).

- **Chat**
  - `GET /api/orders/{order_id}/chat/` – zakaz bo‘yicha chat tarixini ko‘rish.
  - `POST /api/orders/{order_id}/chat/` – foydalanuvchi bilan chat qilish.
  - `ws://localhost/ws/chat/{order_id}/{access_token}/` – real-time chat kanaliga ulanish.

- **Notifications**
  - Kerak bo‘lganda Operator uchun ham server tomondan `Notification` lar yuborilishi mumkin (lekin REST orqali faqat o‘z notificatsiyalarini ko‘ra oladi).

### Dostavchik (Courier)

- **Orders**
  - `GET /api/orders/` – barcha zakazlarni ko‘rish (roliga qarab cheklanadi – odatda o‘ziga biriktirilgan zakazlar).
  - `GET /api/orders/{id}/` – o‘ziga biriktirilgan zakazni ko‘rish.
  - `PATCH /api/orders/{id}/status/` – zakaz holatini yangilash (masalan, `delivering` → `completed` yoki `rejected`).

- **Chat**
  - `GET /api/orders/{order_id}/chat/` – zakaz bo‘yicha chat.
  - `POST /api/orders/{order_id}/chat/` – Operator yoki User bilan yozishish.
  - `ws://localhost/ws/chat/{order_id}/{access_token}/` – real-time chat.

- **Notifications**
  - `GET /api/notifications/`, `GET /api/notifications/unread/`, `PATCH /api/notifications/{id}/read/`.
  - `ws://localhost/ws/notification/{access_token}/` – o‘z notificatsiyalarini real vaqtda olish.
