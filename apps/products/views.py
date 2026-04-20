import json
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db.models import Q

from .models import Badge, Unit, Products, ProductBarcode, ProductImage, ProductSavedUser
from .serializers import (
    BadgeSerializer,
    BadgeCreateUpdateSerializer,
    UnitSerializer,
    UnitCreateUpdateSerializer,
    ProductListSerializer,
    ProductCreateSerializer,
    ProductBarcodeSerializer,
    ProductBarcodeUpdateSerializer,
    ProductImageSerializer,
    ProductImageUpdateSerializer,
    ProductSavedUserSerializer,
)
from .services.barcode import generate_barcode_number, generate_barcode_image


# ========== Badge CRUD ==========

def _apply_translations(obj, translations: dict):
    """Apply translations to a TranslatableModel instance using direct DB access."""
    TranslationModel = obj.translations.model
    
    for lang, data in translations.items():
        if isinstance(data, dict):
            # Get or create translation for this language
            trans, created = TranslationModel.objects.get_or_create(
                master=obj,
                language_code=lang
            )
            # Update fields
            for field, value in data.items():
                if hasattr(trans, field):
                    setattr(trans, field, value)
            trans.save()


@extend_schema_view(
    get=extend_schema(tags=['Бейджи'], summary='Список бейджей'),
    post=extend_schema(
        tags=['Бейджи'],
        summary='Создать бейдж',
        description='Создание нового бейджа с переводами.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'object',
                        'description': 'Переводы названия',
                        'example': {
                            'ru': {'name': 'Новинка'},
                            'uz': {'name': 'Yangi'},
                            'en': {'name': 'New'}
                        }
                    },
                    'is_active': {'type': 'boolean', 'default': True},
                },
                'required': ['name'],
            }
        },
    ),
)
class BadgeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = Badge.objects.prefetch_related('translations').order_by('-created_at')
        return Response(BadgeSerializer(items, many=True).data)

    def post(self, request):
        serializer = BadgeCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        v = serializer.validated_data
        badge = Badge.objects.create(is_active=v.get('is_active', True))
        _apply_translations(badge, v['name'])
        
        # Refresh with translations
        badge = Badge.objects.prefetch_related('translations').get(pk=badge.pk)
        return Response(BadgeSerializer(badge).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=['Бейджи'], summary='Бейдж по ID'),
    put=extend_schema(
        tags=['Бейджи'],
        summary='Обновить бейдж',
        description='Обновление бейджа с переводами.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'object',
                        'description': 'Переводы названия',
                        'example': {
                            'ru': {'name': 'Хит продаж'},
                            'uz': {'name': 'Eng ko\'p sotilgan'},
                            'en': {'name': 'Best Seller'}
                        }
                    },
                    'is_active': {'type': 'boolean'},
                },
            }
        },
    ),
    delete=extend_schema(tags=['Бейджи'], summary='Удалить бейдж'),
)
class BadgeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            badge = Badge.objects.prefetch_related('translations').get(pk=pk)
        except Badge.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BadgeSerializer(badge).data)

    def put(self, request, pk):
        try:
            badge = Badge.objects.get(pk=pk)
        except Badge.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BadgeCreateUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        v = serializer.validated_data
        if 'name' in v:
            _apply_translations(badge, v['name'])
        if 'is_active' in v:
            badge.is_active = v['is_active']
            badge.save()
        
        # Refresh with translations
        badge = Badge.objects.prefetch_related('translations').get(pk=pk)
        return Response(BadgeSerializer(badge).data)

    def delete(self, request, pk):
        try:
            badge = Badge.objects.get(pk=pk)
            badge.delete()
        except Badge.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== Unit CRUD ==========

@extend_schema_view(
    get=extend_schema(tags=['Единицы'], summary='Список единиц'),
    post=extend_schema(
        tags=['Единицы'],
        summary='Создать единицу',
        description='Создание единицы измерения с переводами.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'object',
                        'description': 'Переводы названия',
                        'example': {
                            'ru': {'name': 'кг'},
                            'uz': {'name': 'kg'},
                            'en': {'name': 'kg'}
                        }
                    },
                    'is_active': {'type': 'boolean', 'default': True},
                },
                'required': ['name'],
            }
        },
    ),
)
class UnitListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = Unit.objects.prefetch_related('translations').order_by('-created_at')
        return Response(UnitSerializer(items, many=True).data)

    def post(self, request):
        serializer = UnitCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        v = serializer.validated_data
        unit = Unit.objects.create(is_active=v.get('is_active', True))
        _apply_translations(unit, v['name'])
        
        # Refresh with translations
        unit = Unit.objects.prefetch_related('translations').get(pk=unit.pk)
        return Response(UnitSerializer(unit).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=['Единицы'], summary='Единица по ID'),
    put=extend_schema(
        tags=['Единицы'],
        summary='Обновить единицу',
        description='Обновление единицы измерения с переводами.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'object',
                        'description': 'Переводы названия',
                        'example': {
                            'ru': {'name': 'литр'},
                            'uz': {'name': 'litr'},
                            'en': {'name': 'litre'}
                        }
                    },
                    'is_active': {'type': 'boolean'},
                },
            }
        },
    ),
    delete=extend_schema(tags=['Единицы'], summary='Удалить единицу'),
)
class UnitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            unit = Unit.objects.prefetch_related('translations').get(pk=pk)
        except Unit.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UnitSerializer(unit).data)

    def put(self, request, pk):
        try:
            unit = Unit.objects.get(pk=pk)
        except Unit.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UnitCreateUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        v = serializer.validated_data
        if 'name' in v:
            _apply_translations(unit, v['name'])
        if 'is_active' in v:
            unit.is_active = v['is_active']
            unit.save()
        
        # Refresh with translations
        unit = Unit.objects.prefetch_related('translations').get(pk=pk)
        return Response(UnitSerializer(unit).data)

    def delete(self, request, pk):
        try:
            unit = Unit.objects.get(pk=pk)
            unit.delete()
        except Unit.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== Product ==========

def _parse_product_data(request):
    from django.http import QueryDict
    raw_data = request.data
    if isinstance(raw_data, QueryDict):
        data = {}
        for key in raw_data.keys():
            if key != 'images':
                data[key] = raw_data.get(key)
    else:
        data = dict(raw_data) if raw_data else {}
    
    if 'translations' in data and isinstance(data.get('translations'), str):
        try:
            data['translations'] = json.loads(data['translations'])
        except json.JSONDecodeError:
            pass
    if 'is_discount' in data:
        data['is_discount'] = str(data['is_discount']).lower() in ('true', '1', 'yes')
    if 'is_active' in data:
        data['is_active'] = str(data['is_active']).lower() in ('true', '1', 'yes')
    
    for key in ['badge', 'unit']:
        if key in data:
            val = data[key]
            if val is None or val == '' or str(val).strip() == '':
                del data[key]
            else:
                try:
                    data[key] = int(val)
                except (ValueError, TypeError):
                    del data[key]
    
    if 'category' in data and data['category'] is not None and data['category'] != '':
        try:
            data['category'] = int(data['category'])
        except (ValueError, TypeError):
            data['category'] = None
    
    for key in ['quantity', 'discount_percentage']:
        if key in data and data[key] is not None and data[key] != '':
            try:
                data[key] = int(data[key])
            except (ValueError, TypeError):
                data[key] = 0
    return data


def _apply_product_translations(product, translations):
    fields = ['name', 'description', 'composition', 'expiration_date', 'country', 'grammage']
    for lang, trans in (translations or {}).items():
        if isinstance(trans, dict) and lang in ('ru', 'uz', 'en'):
            for f in fields:
                if f in trans:
                    product.set_current_language(lang)
                    setattr(product, f, trans[f] if trans[f] is not None else '')
            product.save()


def _create_or_update_barcode(product, barcode_number=None):
    if barcode_number is None or barcode_number == '':
        barcode_number = generate_barcode_number()
    img_file = generate_barcode_image(barcode_number)
    pb = ProductBarcode.objects.create(product=product, barcode=barcode_number)
    if img_file:
        pb.barcode_image.save(f'{barcode_number}.png', img_file, save=True)
    return pb


@extend_schema_view(
    get=extend_schema(
        tags=['Продукты'],
        summary='Список продуктов',
        parameters=[
            OpenApiParameter(name='q', type=OpenApiTypes.STR, description='Поиск по названию/описанию/штрихкоду/unique_id'),
            OpenApiParameter(name='category', type=OpenApiTypes.INT),
            OpenApiParameter(name='is_active', type=OpenApiTypes.BOOL),
            OpenApiParameter(name='limit', type=OpenApiTypes.INT, description='Pagination limit'),
            OpenApiParameter(name='offset', type=OpenApiTypes.INT, description='Pagination offset'),
        ],
    ),
    post=extend_schema(
        tags=['Продукты'],
        summary='Создать продукт',
        description='''FormData: translations (JSON-строка), badge, unit, quantity, price, barcode_number (optional), images (multiple).

**translations** поля:
- name: Название продукта
- description: Описание продукта
- composition: Состав продукта
- expiration_date: Срок годности (текстовое поле)
- country: Страна производства
- grammage: Граммаж/вес

**Пример translations:**
```json
{
  "uz": {"name": "Olma", "description": "Yangi olma", "composition": "100% tabiiy", "expiration_date": "2026-12-31", "country": "O'zbekiston", "grammage": "1 kg"},
  "ru": {"name": "Яблоко", "description": "Свежее яблоко", "composition": "100% натуральный", "expiration_date": "2026-12-31", "country": "Узбекистан", "grammage": "1 кг"},
  "en": {"name": "Apple", "description": "Fresh apple", "composition": "100% natural", "expiration_date": "2026-12-31", "country": "Uzbekistan", "grammage": "1 kg"}
}
```''',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'translations': {
                        'type': 'string',
                        'description': 'JSON строка с переводами. Поля: name, description, composition, expiration_date (text), country, grammage',
                        'example': '{"uz": {"name": "Olma", "description": "Yangi olma", "composition": "100% tabiiy", "expiration_date": "2026-12-31", "country": "O\'zbekiston", "grammage": "1 kg"}, "ru": {"name": "Яблоко", "description": "Свежее яблоко", "composition": "100% натуральный", "expiration_date": "2026-12-31", "country": "Узбекистан", "grammage": "1 кг"}, "en": {"name": "Apple", "description": "Fresh apple", "composition": "100% natural", "expiration_date": "2026-12-31", "country": "Uzbekistan", "grammage": "1 kg"}}'
                    },
                    'badge': {'type': 'integer', 'description': 'ID бейджа (опционально, оставьте пустым если нет)', 'nullable': True},
                    'unit': {'type': 'integer', 'description': 'ID единицы измерения (опционально, оставьте пустым если нет)', 'nullable': True},
                    'category': {'type': 'integer', 'description': 'ID категории (обязательно)', 'example': 1},
                    'quantity': {'type': 'integer', 'description': 'Количество на складе', 'default': 0, 'example': 100},
                    'price': {'type': 'number', 'description': 'Цена (обязательно)', 'example': 15000.00},
                    'price_discount': {'type': 'number', 'description': 'Цена со скидкой', 'example': 12000.00},
                    'discount_percentage': {'type': 'integer', 'description': 'Процент скидки', 'default': 0, 'example': 20},
                    'is_discount': {'type': 'boolean', 'description': 'Есть ли скидка', 'default': False, 'example': True},
                    'is_active': {'type': 'boolean', 'description': 'Активен ли продукт', 'default': True, 'example': True},
                    'barcode_number': {'type': 'string', 'description': 'Штрихкод (если пусто - генерируется автоматически)', 'example': '4780001234567'},
                    'images': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'}, 'description': 'Изображения продукта (можно несколько)'},
                },
                'required': ['translations', 'category', 'price'],
            }
        },
    ),
)
class ProductListCreateView(APIView):
    pagination_class = LimitOffsetPagination

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        from apps.categories.models import Category
        
        qs = Products.objects.all().order_by('-created_at')
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(unique_id__icontains=q)
                | Q(barcodes__barcode__icontains=q)
                | Q(translations__name__icontains=q)
                | Q(translations__description__icontains=q)
            ).distinct()
        cat = request.query_params.get('category')
        if cat:
            category_ids = self._get_category_with_descendants(int(cat))
            qs = qs.filter(category_id__in=category_ids)
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=str(is_active).lower() in ('true', '1', 'yes'))

        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is None:
            return Response(ProductListSerializer(qs, many=True, context={'request': request}).data)
        serializer = ProductListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)
    
    def _get_category_with_descendants(self, category_id):
        from apps.categories.models import Category
        
        ids = [category_id]
        children = Category.objects.filter(parent_id=category_id, is_active=True).values_list('id', flat=True)
        for child_id in children:
            ids.extend(self._get_category_with_descendants(child_id))
        return ids

    def post(self, request):
        data = _parse_product_data(request)
        data['badge'] = data.get('badge')
        data['unit'] = data.get('unit')
        data['category'] = data.get('category')
        data['barcode_number'] = data.get('barcode_number') or ''

        serializer = ProductCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v = serializer.validated_data
        product = Products.objects.create(
            badge=v.get('badge'),
            unit=v.get('unit'),
            shelf_location=v.get('shelf_location'),
            quantity=v.get('quantity', 0),
            price=v['price'],
            price_discount=v.get('price_discount'),
            discount_percentage=v.get('discount_percentage', 0),
            is_discount=v.get('is_discount', False),
            is_active=v.get('is_active', True),
            category=v['category'],
        )
        _apply_product_translations(product, v.get('translations'))
        barcode_num = data.get('barcode_number')
        _create_or_update_barcode(product, barcode_num if barcode_num else None)
        for img in request.FILES.getlist('images'):
            ProductImage.objects.create(product=product, image=img)

        serializer_out = ProductListSerializer(product, context={'request': request})
        return Response(serializer_out.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=['Продукты'], summary='Продукт по ID'),
    put=extend_schema(
        tags=['Продукты'],
        summary='Обновить продукт',
        description='''FormData: translations (JSON-строка), badge, unit, quantity, price, images (multiple). Все поля опциональны.

**translations** поля:
- name: Название продукта
- description: Описание продукта
- composition: Состав продукта
- expiration_date: Срок годности (текстовое поле)
- country: Страна производства
- grammage: Граммаж/вес

**Пример translations:**
```json
{
  "uz": {"name": "Olma", "description": "Yangi olma"},
  "ru": {"name": "Яблоко", "description": "Свежее яблоко"}
}
```''',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'translations': {
                        'type': 'string',
                        'description': 'JSON строка с переводами. Поля: name, description, composition, expiration_date (text), country, grammage',
                        'example': '{"uz": {"name": "Olma", "description": "Yangi olma"}, "ru": {"name": "Яблоко", "description": "Свежее яблоко"}}'
                    },
                    'badge': {'type': 'integer', 'description': 'ID бейджа (опционально)', 'nullable': True},
                    'unit': {'type': 'integer', 'description': 'ID единицы измерения (опционально)', 'nullable': True},
                    'category': {'type': 'integer', 'description': 'ID категории'},
                    'quantity': {'type': 'integer', 'description': 'Количество на складе', 'example': 100},
                    'price': {'type': 'number', 'description': 'Цена', 'example': 15000.00},
                    'price_discount': {'type': 'number', 'description': 'Цена со скидкой', 'example': 12000.00},
                    'discount_percentage': {'type': 'integer', 'description': 'Процент скидки', 'example': 20},
                    'is_discount': {'type': 'boolean', 'description': 'Есть ли скидка', 'example': True},
                    'is_active': {'type': 'boolean', 'description': 'Активен ли продукт', 'example': True},
                    'replace_images': {'type': 'boolean', 'description': 'Если true — новые изображения заменят старые. Если false/не указано — добавятся к текущим.', 'example': False},
                    'images': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'}, 'description': 'Изображения продукта (по умолчанию добавятся, а не заменят)'},
                },
            }
        },
    ),
    delete=extend_schema(tags=['Продукты'], summary='Удалить продукт'),
)
class ProductDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        try:
            product = Products.objects.get(pk=pk)
        except Products.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductListSerializer(product, context={'request': request})
        return Response(serializer.data)

    def put(self, request, pk):
        try:
            product = Products.objects.get(pk=pk)
        except Products.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        data = _parse_product_data(request)
        serializer = ProductCreateSerializer(data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v = serializer.validated_data
        for field in ['shelf_location', 'quantity', 'price', 'price_discount', 'discount_percentage', 'is_discount', 'is_active']:
            if field in v:
                setattr(product, field, v[field])
        
        if 'badge' in v and v['badge'] is not None:
            product.badge = v['badge']
        if 'unit' in v and v['unit'] is not None:
            product.unit = v['unit']
        if 'category' in v and v['category'] is not None:
            product.category = v['category']
        
        product.save()
        if 'translations' in v:
            _apply_product_translations(product, v['translations'])
        if request.FILES.getlist('images'):
            # Default behavior: append new images and keep old ones.
            # To replace existing images, pass replace_images=true (form field or query param).
            replace_images_flag = request.data.get('replace_images', None)
            if replace_images_flag is None:
                replace_images_flag = request.query_params.get('replace_images', None)
            replace_images = str(replace_images_flag).lower() in ('true', '1', 'yes', 'y', 'on')

            if replace_images:
                product.images.all().delete()
            for img in request.FILES.getlist('images'):
                ProductImage.objects.create(product=product, image=img)

        return Response(ProductListSerializer(product, context={'request': request}).data)

    def delete(self, request, pk):
        try:
            product = Products.objects.get(pk=pk)
            product.delete()
        except Products.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== ProductBarcode ==========

@extend_schema_view(
    put=extend_schema(
        tags=['Штрихкоды'],
        summary='Обновить штрихкод',
        description='Обновление штрихкода продукта. Изображение генерируется автоматически.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'barcode': {'type': 'string', 'description': '12-значный номер штрихкода', 'example': '123456789012'},
                },
                'required': ['barcode'],
            }
        },
    ),
    delete=extend_schema(tags=['Штрихкоды'], summary='Удалить штрихкод'),
)
class ProductBarcodeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            pb = ProductBarcode.objects.get(pk=pk)
        except ProductBarcode.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductBarcodeUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        barcode_num = serializer.validated_data['barcode']
        img_file = generate_barcode_image(barcode_num)
        pb.barcode = barcode_num
        if img_file:
            pb.barcode_image.save(f'{barcode_num}.png', img_file, save=True)
        pb.save()
        return Response(ProductBarcodeSerializer(pb).data)

    def delete(self, request, pk):
        try:
            ProductBarcode.objects.get(pk=pk).delete()
        except ProductBarcode.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== ProductImage ==========

@extend_schema_view(
    put=extend_schema(
        tags=['Изображения продуктов'],
        summary='Обновить изображение',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'image': {'type': 'string', 'format': 'binary', 'description': 'Новое изображение'},
                },
                'required': ['image'],
            }
        },
    ),
    delete=extend_schema(tags=['Изображения продуктов'], summary='Удалить изображение'),
)
class ProductImageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            pi = ProductImage.objects.get(pk=pk)
        except ProductImage.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if not request.FILES.get('image'):
            return Response({'image': ['Обязательное поле.']}, status=status.HTTP_400_BAD_REQUEST)
        pi.image = request.FILES['image']
        pi.save()
        return Response(ProductImageSerializer(pi, context={'request': request}).data)

    def delete(self, request, pk):
        try:
            ProductImage.objects.get(pk=pk).delete()
        except ProductImage.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== ProductSavedUser ==========

@extend_schema_view(
    get=extend_schema(tags=['Сохранённые'], summary='Мои сохранённые продукты'),
    post=extend_schema(
        tags=['Сохранённые'],
        summary='Сохранить продукт',
        description='Сохранить продукт в избранное',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'product': {'type': 'integer', 'description': 'ID продукта', 'example': 1},
                },
                'required': ['product'],
            }
        },
    ),
)
class ProductSavedListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved = ProductSavedUser.objects.filter(user=request.user, is_active=True).order_by('-created_at')
        serializer = ProductSavedUserSerializer(saved, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        product_id = request.data.get('product')
        if not product_id:
            return Response({'product': ['Обязательное поле.']}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Products.objects.get(pk=product_id)
        except Products.DoesNotExist:
            return Response({'product': ['Не найден']}, status=status.HTTP_400_BAD_REQUEST)

        obj, created = ProductSavedUser.objects.get_or_create(
            product=product, user=request.user, defaults={'is_active': True}
        )
        if not created:
            obj.is_active = True
            obj.save()

        serializer = ProductSavedUserSerializer(obj, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Сохранённые'],
    summary='Удалить из сохранённых',
    description='Удалить продукт из избранного по ID продукта',
    parameters=[
        OpenApiParameter(name='product_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH, description='ID продукта'),
    ],
)
class ProductSavedDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        try:
            ProductSavedUser.objects.get(product_id=product_id, user=request.user).delete()
        except ProductSavedUser.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
