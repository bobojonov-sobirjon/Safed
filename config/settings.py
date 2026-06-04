"""
Django settings for Safed project.
Production-ready configuration with security best practices.
"""
import os
from datetime import timedelta
from pathlib import Path
from typing import List

# Daphne/ASGI da sync ORM (JWT auth, DRF) ishlashi uchun
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# Allowed hosts from environment
_allowed_hosts = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS: List[str] = [h.strip() for h in _allowed_hosts.split(',') if h.strip()]

# Security headers (production uchun)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

LOCAL_APPS = [
    'apps.core',
    'apps.accounts',
    'apps.categories',
    'apps.products',
    'apps.orders',
    'apps.news',
    'apps.realtime',
    'apps.inventory',
]

THIRD_PARTY_APPS = [
    'channels',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'corsheaders',
    'django_filters',
    'parler',
    *LOCAL_APPS,
]

INSTALLED_APPS = [
    'daphne',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    *THIRD_PARTY_APPS,
]

# =============================================================================
# MIDDLEWARE
# =============================================================================

LOCAL_MIDDLEWARE = [
    'config.middleware.middleware.JsonErrorResponseMiddleware',
    'config.middleware.middleware.Custom404Middleware',
    'config.middleware.throttle.RateLimitMiddleware',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    *LOCAL_MIDDLEWARE,
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'client_encoding': 'UTF8',
        },
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# CACHING
# =============================================================================

CACHES = {
    'default': {
        'BACKEND': os.getenv('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache'),
        'LOCATION': os.getenv('CACHE_LOCATION', 'unique-snowflake'),
        'TIMEOUT': 300,  # 5 minutes default
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# Cache timeouts (seconds)
CACHE_TTL_SHORT = 60  # 1 minute
CACHE_TTL_MEDIUM = 300  # 5 minutes
CACHE_TTL_LONG = 3600  # 1 hour
CACHE_TTL_DAY = 86400  # 24 hours

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# Fallback when a date has no "Рабочие часы по дням" row in DB (see BusyDayWorkingHours model).
BUSY_SLOT_WORKING_START = os.getenv('BUSY_SLOT_WORKING_START', '06:00')
BUSY_SLOT_WORKING_END = os.getenv('BUSY_SLOT_WORKING_END', '23:00')

LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "/var/www/media/")

# WhiteNoise for static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =============================================================================
# AUTHENTICATION
# =============================================================================

SITE_ID = 1
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] + (['rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else []),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Test / frontend ulanish uchun yumshoqroq (prod: .env bilan qisqartirish mumkin)
        'anon': os.getenv('THROTTLE_ANON', '1000/minute'),
        'user': os.getenv('THROTTLE_USER', '5000/minute'),
        'login': os.getenv('THROTTLE_LOGIN', '30/minute'),
        'otp': os.getenv('THROTTLE_OTP', '15/minute'),
    },
    'PAGE_SIZE': 20,
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# =============================================================================
# JWT SETTINGS
# =============================================================================

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# =============================================================================
# CORS SETTINGS
# =============================================================================

_cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:8000, https://apies.firepole.ru')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]

CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only in development
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS.copy()

# =============================================================================
# API DOCUMENTATION (DRF Spectacular)
# =============================================================================

from apps.orders.openapi_tags import ORDER_OPENAPI_TAGS

SPECTACULAR_SETTINGS = {
    'TITLE': 'Safed API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/v1',
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'DISABLE_ERRORS_AND_WARNINGS': True,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayRequestDuration': True,
        'filter': True,
        'tryItOutEnabled': True,
    },
    'DESCRIPTION': """
## Safed — мобильный бэкенд (API v1)

Базовый префикс: **`/api/v1/`**.

### Авторизация
Большинство методов требуют **JWT** в заголовке: `Authorization: Bearer <access_token>`.
Получение токена — раздел **«Авторизация»** (OTP / логин по телефону).

### Buyurtma (Swagger tartibi — `01` … `12 Order`)
1. **01 Delivery Slots** — `GET /checkout/delivery-slots/` (yoki `/busy-slots/`)
2. **02 Addresses** — `GET/POST /addresses/`
3. **03 Pricing Preview** — `POST /checkout/pricing-preview/`
4. **04 Create Order** — `POST /orders/` (`payment_type`: card | cash)
5. **05 Payment** — `POST /orders/{id}/click-payment/` (card); CLICK callbacks `payments/click/prepare|complete`
6. **06 My Orders** — `GET /orders/my/`, `POST /orders/{id}/cancel/`
7. **07 Picking** — `PATCH picking-lines`, `POST picking/scan` (staff)
8. **08 Admin Operations** — status, courier, lists
9. **09 Courier** — `GET /orders/courier/my/`
10. **10 Order Detail** — `GET/PUT/DELETE /orders/{id}/`

### Статусы заказа
`created` → `confirmed` → `picking` → `shipped` → `delivered`, а также `rejected`, `cancelled`.
Отмена пользователем: `POST /orders/<id>/cancel/` только в `created` (comment и/или `reason_ids`).

### Cash (naqd)
- QR faqat `GET /orders/my/` → `cash_qr_code` (pending cash).
- Kuryer: `PATCH /orders/cash/confirm/` (`order_id`, `qr_code`) — status `shipped`, paid + delivered.
- WebSocket: `ws/orders/delivery/?token=<JWT>` — cash delivery events (order_id body da).

### Роли
Группы Django: **Super Admin**, **Admin**, **Operator**, **Courier**, **User** — доступ к разделам зависит от роли (см. описания тегов ниже).

### Qaysi `id` nima? (muhim)
| Qayerda | Maydon | Ma’nosi |
|---------|--------|---------|
| URL `/orders/{id}/` | **`id`** | **Buyurtma ID** — `POST /orders/` yoki `GET /orders/my/` → `"id": 4` |
| URL `.../picking-lines/{line_id}/` | **`line_id`** | **Qator ID** — `GET /orders/{id}/` → `order_products[].id` (masalan `2`) |
| Body `products_data[]` | **`product_id`** | **Katalog mahsulot** — `Products.id` |
| Javob `order_products[]` | **`id`** | = `line_id` (qator) |
| Javob `order_products[]` | **`product_id`** | = katalog mahsulot |
| `/addresses/{pk}/` | **`pk`** | Saqlangan manzil ID |
""",
    'TAGS': ORDER_OPENAPI_TAGS + [
        {'name': 'Инвентаризация / Поставщики', 'description': 'Справочник поставщиков (Super Admin / Admin).'},
        {'name': 'Инвентаризация / Приходы', 'description': 'Приходные документы и заголовки.'},
        {'name': 'Инвентаризация / Позиции прихода', 'description': 'Строки прихода, штрихкоды при приёмке.'},
        {'name': 'Инвентаризация / Штрихкоды', 'description': 'Поиск товара по штрихкоду.'},
        {'name': 'Посты', 'description': 'Новости и посты (контент).'},
        {'name': 'Изображения постов', 'description': 'Медиа к постам.'},
        {'name': 'Products', 'description': 'Каталог: список и детали товаров для приложения.'},
        {'name': 'Products (Admin)', 'description': 'Управление товарами и медиа (админ).'},
        {'name': 'Бейджи', 'description': 'Бейджи товаров (переводы Parler).'},
        {'name': 'Единицы', 'description': 'Единицы измерения (переводы).'},
        {'name': 'Штрихкоды', 'description': 'Штрихкоды продуктов.'},
        {'name': 'Изображения продуктов', 'description': 'Изображения каталога.'},
        {'name': 'Сохранённые', 'description': 'Избранное пользователя.'},
        {'name': 'Категории', 'description': 'Дерево категорий и CRUD (по ролям).'},
        {'name': 'Chat', 'description': 'Чаты и сообщения (realtime).'},
        {'name': 'Notifications', 'description': 'Уведомления пользователя: список, непрочитанные, отметка прочитанным.'},
        {'name': 'Авторизация', 'description': 'OTP, токены JWT, регистрация.'},
        {'name': 'Админ', 'description': 'Создание пользователей админом, служебные действия.'},
        {'name': 'Пользователи', 'description': 'Профиль и данные текущего пользователя.'},
        {'name': 'Персонал', 'description': 'Управление пользователями для персонала (по ролям).'},
        {'name': 'Обычный пользователь', 'description': 'Назначение роли User.'},
        {'name': 'Простой администратор', 'description': 'Назначение роли Admin.'},
        {'name': 'Оператор', 'description': 'Назначение роли Operator.'},
        {'name': 'Курьер', 'description': 'Назначение роли Courier.'},
        {'name': 'Устройства', 'description': 'Push-устройства (FCM и т.п.).'},
    ],
}

# =============================================================================
# PARLER (Translations)
# =============================================================================

PARLER_DEFAULT_LANGUAGE_CODE = 'ru'
PARLER_LANGUAGES = {
    None: (
        {'code': 'ru'},
        {'code': 'uz'},
        {'code': 'en'},
    ),
    'default': {
        'fallbacks': ['ru'],
        'hide_untranslated': False,
    }
}

# =============================================================================
# CHANNELS (WebSockets)
# =============================================================================

_use_redis = os.getenv('CHANNEL_LAYERS_REDIS', 'false').lower() == 'true'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [os.getenv('REDIS_URL', 'redis://localhost:6379/1')]},
    } if _use_redis else {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# =============================================================================
# CELERY (background tasks — optional)
# =============================================================================

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/2'))
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# Kunlik savat eslatmasi push (FCM, o‘zbekcha) — har kuni 10:00 Toshkent
DAILY_CART_REMINDER_ENABLED = os.getenv('DAILY_CART_REMINDER_ENABLED', 'True').lower() in (
    'true',
    '1',
    'yes',
)
DAILY_CART_REMINDER_HOUR = int(os.getenv('DAILY_CART_REMINDER_HOUR', '10'))
DAILY_CART_REMINDER_MINUTE = int(os.getenv('DAILY_CART_REMINDER_MINUTE', '0'))

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {}
if DAILY_CART_REMINDER_ENABLED:
    CELERY_BEAT_SCHEDULE['daily-cart-reminder-push'] = {
        'task': 'apps.realtime.tasks.send_daily_cart_reminder_push',
        'schedule': crontab(
            hour=DAILY_CART_REMINDER_HOUR,
            minute=DAILY_CART_REMINDER_MINUTE,
        ),
    }

# =============================================================================
# INVENTORY
# =============================================================================

LOW_STOCK_THRESHOLD = int(os.getenv('LOW_STOCK_THRESHOLD', '5'))

# =============================================================================
# RATE LIMITING
# =============================================================================

RATE_LIMIT_ENABLE = os.getenv('RATE_LIMIT_ENABLE', 'True').lower() in ('true', '1', 'yes')
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '2000'))  # per IP per window
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # seconds

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'formatter': 'verbose',
        } if os.path.exists(os.path.join(BASE_DIR, 'logs')) else {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# =============================================================================
# CLICK (https://docs.click.uz/)
# =============================================================================

CLICK_SERVICE_ID = int(os.getenv('CLICK_SERVICE_ID', '101345') or '0')
CLICK_MERCHANT_ID = int(os.getenv('CLICK_MERCHANT_ID', '38156') or '0')
CLICK_SECRET_KEY = os.getenv('CLICK_SECRET_KEY', '')
CLICK_MERCHANT_USER_ID = int(os.getenv('CLICK_MERCHANT_USER_ID', '82888') or '0') or None
CLICK_PAY_URL = os.getenv('CLICK_PAY_URL', 'https://my.click.uz/services/pay')
CLICK_RETURN_URL = os.getenv('CLICK_RETURN_URL', '')

# =============================================================================
# Firebase (FCM) — service account from .env yoki JSON fayl
# =============================================================================

def _normalize_firebase_private_key(raw: str) -> str:
    """`.env` / systemd: bir qatorda `\\n` yoki haqiqiy yangi qator."""
    key = (raw or '').strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in ('"', "'"):
        key = key[1:-1]
    key = key.replace('\r\n', '\n').replace('\r', '\n')
    if '\\n' in key:
        key = key.replace('\\n', '\n')
    return key


FIREBASE_CREDENTIALS_FILE = os.getenv('FIREBASE_CREDENTIALS_FILE', '')
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', '')
FIREBASE_PRIVATE_KEY_ID = os.getenv('FIREBASE_PRIVATE_KEY_ID', '')
FIREBASE_CLIENT_EMAIL = os.getenv('FIREBASE_CLIENT_EMAIL', '')
FIREBASE_CLIENT_ID = os.getenv('FIREBASE_CLIENT_ID', '')
FIREBASE_PRIVATE_KEY = _normalize_firebase_private_key(os.getenv('FIREBASE_PRIVATE_KEY', ''))
FIREBASE_AUTH_URI = os.getenv('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth')
FIREBASE_TOKEN_URI = os.getenv('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token')
FIREBASE_AUTH_PROVIDER_CERT_URL = os.getenv(
    'FIREBASE_AUTH_PROVIDER_CERT_URL',
    'https://www.googleapis.com/oauth2/v1/certs',
)
FIREBASE_CLIENT_CERT_URL = (
    os.getenv('FIREBASE_CLIENT_CERT_URL', '')
    or os.getenv('FIREBASE_CLIENT_X509_CERT_URL', '')
)
FIREBASE_UNIVERSE_DOMAIN = os.getenv('FIREBASE_UNIVERSE_DOMAIN', 'googleapis.com')
