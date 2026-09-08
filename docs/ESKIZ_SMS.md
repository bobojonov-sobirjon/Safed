# Eskiz SMS — server sozlamasi

Login OTP Eskiz orqali yuboriladi.

## Server `.env` (majburiy)

```env
ESKIZ_EMAIL=faraganiev@gmail.com
ESKIZ_PASSWORD=<API_SECRET>
ESKIZ_FROM=4546
ESKIZ_OTP_TEMPLATE=Safet Go mobil ilovasiga kirish uchun tasdiqlash kodi: {code}. Kodni hech kimga bermang
OTP_TEST_CODE=
```

**Muhim:** `ESKIZ_PASSWORD` — web kabinet paroli emas, Eskiz bergan **API secret**.

## Flow

1. `POST /api/v1/auth/login/` `{ "phone": "99890..." }`
2. Backend random OTP yaratadi → Eskiz SMS (tasdiqlangan shablon)
3. `POST /api/v1/auth/verify-otp/` `{ "phone": "...", "code": "...." }` → JWT

## Test mode

```env
OTP_TEST_CODE=1111
```

bo‘lsa SMS ketmaydi, kod har doim `1111`.

## Deploy checklist

1. Kod push (`.env` git’ga **kirmaydi**)
2. Serverda `.env` ga `ESKIZ_*` qo‘ying
3. `OTP_TEST_CODE=` bo‘sh
4. App/gunicorn restart
5. Haqiqiy raqam bilan login sinang
