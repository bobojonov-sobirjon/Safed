"""Swagger descriptions for order endpoints."""

ORDER_CREATE_DESCRIPTION = """
Создаёт заказ: статус **`created`**, оплата **`pending`**.

---

## 1. Товары — `products_data[]`

| Поле | Обязательно | Описание |
|------|-------------|----------|
| **`product_id`** | да | ID из каталога `GET /products/` (поле `id`). **Не** путать с `order id` или `line_id`. |
| **`quantity`** | да | Сколько берёт клиент (в единицах ниже или в `product_unit`). |
| **`product_unit`** | нет | `piece`, `kg`, `gram`, `liter`, `ml`. Если не передать — берётся из карточки товара. Справка: **`GET /products/unit-options/`** |

**`total_price` не передавать** — сервер считает: `(normalized_qty ÷ unit_amount) × price` товара.

**Swagger multipart:** можно одной строкой JSON:
`-F 'products_data={"product_id":5,"quantity":"1.5","product_unit":"kg"}'`
или массив: `-F 'products_data=[{"product_id":5},{"product_id":6}]'`
Либо **`Content-Type: application/json`** (рекомендуется для мобильного API).

### Примеры строк корзины (demo id из seed)

**Картофель (kg), 1.5 кг:**
```json
{ "product_id": 5, "quantity": "1.5", "product_unit": "kg" }
```

**Cola 0.5L — 2 бутылки (piece):**
```json
{ "product_id": 10, "quantity": "2", "product_unit": "piece" }
```

**Cola — 500 ml:**
```json
{ "product_id": 10, "quantity": "500", "product_unit": "ml" }
```

**Яйца — 1 упаковка (шт):**
```json
{ "product_id": 12, "quantity": "1", "product_unit": "piece" }
```

### Правила `quantity`

| Тип товара | `quantity` |
|------------|------------|
| **piece** | целое: 1, 2, 3 |
| **kg / liter** | можно дробное: 1.5 |
| **gram / ml** | число в граммах/мл; можно kg↔gram, liter↔ml (конвертация на сервере) |

---

## 2. Адрес (один вариант)

**A)** `delivery_address_id` — сохранённый адрес пользователя (`GET /addresses/`).

**B)** Вместе: **`lat`**, **`long`**, **`address`** (текст).

Опционально: `entrance`, `apartment`, `comment`, `leave_at_door`.

---

## 3. Слот доставки

Из **`GET /checkout/delivery-slots/`** (или `/busy-slots/`) — слот с `available: true`.

Передать **все три** поля:
- `delivery_date` — `YYYY-MM-DD`
- `delivery_time_start` — `09:00` (поле `start` из `slots[]`)
- `delivery_time_end` — `10:00` (поле `end`)

---

## 4. Оплата и баллы

| Поле | Значения |
|------|----------|
| **`payment_type`** | `card` — потом `POST /orders/{id}/click-payment/` → `payment_url`; после оплаты: `confirmed`, `paid`. `cash` — оплата при получении. |
| **`loyalty_points_to_use`** | Списать баллы (скидка UZS; макс. **50%** суммы до скидки и не больше баланса). |

Перед заказом можно проверить суммы: **`POST /checkout/pricing-preview/`** (тот же `products_data`).

---

## 5. Ответ `201`

| Блок | Содержимое |
|------|------------|
| **`id`** | ID заказа → в URL `/orders/{id}/`, click-payment, cancel |
| **`order_pricing`** | `estimated_total`, сборы, скидка, `can_checkout` |
| **`delivery_slot`** | дата, время, адрес |
| **`order_products[]`** | `id` = **line_id** для picking; `product_id` = каталог; `normalized_quantity`, `total_price` |

---

## 6. Ошибки `400`

- Минимальная сумма корзины не достигнута
- Слот недоступен (`full` / `cutoff`)
- Нет товара на складе
- Несовместимые единицы (например kg ↔ liter)
- Недостаточно баллов
- Неверный адрес / слот / валидация полей
"""

PRICING_PREVIEW_DESCRIPTION = """
Превью корзины **без создания заказа** (экран «Сават»).

Тело как у **`POST /orders/`** для товаров и слота:
- `products_data[]` — `product_id`, `quantity`, `product_unit` (опционально). **`total_price` не нужен.**
- `delivery_date`, `delivery_time_start`, `delivery_time_end` — опционально, **все три вместе**
- `loyalty_points_to_use` — опционально

Справка по единицам: **`GET /products/unit-options/`**

Ответ: `products_subtotal`, `delivery_fee`, `estimated_total`, `min_order_met`, `can_checkout`, …
"""
