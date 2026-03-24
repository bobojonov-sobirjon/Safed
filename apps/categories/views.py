import json
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Category
from .serializers import (
    CategoryTreeSerializer,
    CategoryDetailSerializer,
    CategoryCreateSerializer,
    ChildCategoryCreateSerializer,
    CategoryUpdateSerializer,
    CategoryHomeListSerializer,
    CategoryHomeOrderAssignSerializer,
)



TRANSLATIONS_EXAMPLE = {
    "uz": {"name": "Telefon"},
    "ru": {"name": "Телефон"},
    "en": {"name": "Phone"},
}

CATEGORY_RESPONSE_EXAMPLE = {
    "id": 1,
    "name": {"uz": {"name": "Telefon"}, "ru": {"name": "Телефон"}, "en": {"name": "Phone"}},
    "icon": "/media/categories/icons/icon.png",
    "is_active": True,
    "order": 0,
    "child_category": [
        {
            "id": 2,
            "name": {"uz": {"name": "Smartfon"}, "ru": {"name": "Смартфон"}, "en": {"name": "Smartphone"}},
            "icon": None,
            "is_active": True,
            "order": 0,
            "child_category": []
        }
    ]
}


@extend_schema_view(
    get=extend_schema(
        tags=['Категории'],
        summary='Список категорий',
        description='Иерархический список всех категорий с вложенными дочерними категориями. Поддерживает фильтрацию по родительской категории и названию.',
        parameters=[
            OpenApiParameter(
                name='parent',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID родительской категории. Возвращает только дочерние категории указанной категории.',
                required=False
            ),
            OpenApiParameter(
                name='category',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID категории. Возвращает саму категорию с её дочерними категориями.',
                required=False
            ),
            OpenApiParameter(
                name='name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Поиск по названию категории (на любом языке)',
                required=False
            ),
        ],
    ),
    post=extend_schema(
        tags=['Категории'],
        summary='Добавить корневую категорию',
        description='''Создание новой корневой категории.

**Поля:**
- `translations` - JSON-строка с переводами (обязательно)
- `icon` - иконка категории (опционально)
- `is_active` - активна ли категория (по умолчанию true)
- `order` - порядок сортировки (по умолчанию 0)

**Структура translations:**
```json
{"uz": {"name": "Elektronika"}, "ru": {"name": "Электроника"}, "en": {"name": "Electronics"}}
```
''',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'translations': {
                        'type': 'string',
                        'description': 'JSON-строка с переводами',
                        'example': '{"uz": {"name": "Elektronika"}, "ru": {"name": "Электроника"}, "en": {"name": "Electronics"}}',
                    },
                    'icon': {'type': 'string', 'format': 'binary', 'description': 'Иконка категории'},
                    'is_active': {'type': 'boolean', 'default': True, 'example': True},
                    'order': {'type': 'integer', 'default': 0, 'example': 1},
                },
                'required': ['translations'],
            }
        },
    ),
)
class CategoryListCreateView(APIView):
    """GET: ro'yxat (filter bilan), POST: root category qo'shish (FormData + icon)"""
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        parent_id = request.query_params.get('parent')
        category_id = request.query_params.get('category')
        name = request.query_params.get('name')

        if category_id:
            # category= parametr: shu kategoriyani o'zi va uning childlari qaytadi
            try:
                queryset = Category.objects.filter(pk=int(category_id))
            except (ValueError, TypeError):
                queryset = Category.objects.none()
        elif parent_id:
            # parent= parametr: faqat shu parent ning childlarini qaytaradi
            try:
                queryset = Category.objects.filter(parent_id=int(parent_id))
            except (ValueError, TypeError):
                queryset = Category.objects.none()
        else:
            queryset = Category.objects.filter(parent__isnull=True)

        if name:
            queryset = queryset.filter(translations__name__icontains=name).distinct()
        queryset = queryset.order_by('order')

        serializer = CategoryTreeSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        if not (request.content_type and 'multipart/form-data' in request.content_type):
            return Response(
                {'detail': 'Требуется Content-Type: multipart/form-data (для иконки)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        translations_raw = request.data.get('translations')
        if isinstance(translations_raw, str):
            try:
                translations = json.loads(translations_raw)
            except json.JSONDecodeError:
                return Response(
                    {'translations': ['Неверный формат JSON']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            translations = translations_raw or {}
        data = {
            'translations': translations,
            'icon': request.FILES.get('icon'),
            'is_active': request.data.get('is_active', 'true').lower() in ('true', '1', 'yes'),
            'order': int(request.data.get('order') or 0),
        }
        serializer = CategoryCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        category = serializer.save()
        output = CategoryDetailSerializer(category, context={'request': request})
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Категории'],
    summary='Добавить дочернюю категорию',
    description='''Создание дочерней категории.

**Поля:**
- `parent` - ID родительской категории (обязательно)
- `translations` - JSON-строка с переводами (обязательно)
- `icon` - иконка категории (опционально)
- `is_active` - активна ли категория (по умолчанию true)
- `order` - порядок сортировки (по умолчанию 0)
''',
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'parent': {'type': 'integer', 'description': 'ID родительской категории', 'example': 1},
                'translations': {
                    'type': 'string',
                    'description': 'JSON-строка с переводами',
                    'example': '{"uz": {"name": "Smartfonlar"}, "ru": {"name": "Смартфоны"}, "en": {"name": "Smartphones"}}',
                },
                'icon': {'type': 'string', 'format': 'binary', 'description': 'Иконка категории'},
                'is_active': {'type': 'boolean', 'default': True, 'example': True},
                'order': {'type': 'integer', 'default': 0, 'example': 1},
            },
            'required': ['parent', 'translations']
        }
    },
)
class ChildCategoryCreateView(APIView):
    """POST: child category qo'shish (FormData + icon)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.content_type and 'multipart/form-data' in request.content_type):
            return Response(
                {'detail': 'Требуется Content-Type: multipart/form-data'},
                status=status.HTTP_400_BAD_REQUEST
            )
        translations_raw = request.data.get('translations')
        if isinstance(translations_raw, str):
            try:
                translations = json.loads(translations_raw)
            except json.JSONDecodeError:
                return Response(
                    {'translations': ['Неверный формат JSON']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            translations = translations_raw or {}
        parent_id = request.data.get('parent')
        if not parent_id:
            return Response({'parent': ['Обязательное поле']}, status=status.HTTP_400_BAD_REQUEST)
        try:
            parent = Category.objects.get(pk=int(parent_id))
        except (ValueError, Category.DoesNotExist):
            return Response({'parent': ['Категория не найдена']}, status=status.HTTP_400_BAD_REQUEST)
        data = {
            'parent': parent.pk,
            'translations': translations,
            'icon': request.FILES.get('icon'),
            'is_active': str(request.data.get('is_active', 'true')).lower() in ('true', '1', 'yes'),
            'order': int(request.data.get('order') or 0),
        }
        serializer = ChildCategoryCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        category = serializer.save()
        output = CategoryDetailSerializer(category, context={'request': request})
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=['Категории'],
        summary='Получить категорию по ID',
        description='Детальная информация о категории с вложенными дочерними категориями.',
    ),
    put=extend_schema(
        tags=['Категории'],
        summary='Обновить категорию',
        description='''Обновление категории. Все поля опциональны.

**Примечание:** Только отправленные поля будут обновлены.
''',
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'translations': {
                        'type': 'string',
                        'description': 'JSON-строка с переводами',
                        'example': '{"uz": {"name": "Yangi nom"}, "ru": {"name": "Новое название"}}',
                    },
                    'icon': {'type': 'string', 'format': 'binary', 'description': 'Новая иконка'},
                    'is_active': {'type': 'boolean', 'example': True},
                    'order': {'type': 'integer', 'example': 2},
                },
            }
        },
    ),
    delete=extend_schema(
        tags=['Категории'],
        summary='Удалить категорию',
        description='Удаление категории по ID. Все дочерние категории также будут удалены (CASCADE).',
    ),
)
class CategoryDetailUpdateDeleteView(APIView):
    """GET, PUT, DELETE by id"""
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Категория не найдена'}, status=404)
        serializer = CategoryDetailSerializer(category, context={'request': request})
        return Response(serializer.data)

    def put(self, request, pk):
        if request.content_type and 'multipart/form-data' in (request.content_type or ''):
            data = {}
            if 'translations' in request.data:
                tr = request.data.get('translations')
                data['translations'] = json.loads(tr) if isinstance(tr, str) else tr
            if 'icon' in request.FILES:
                data['icon'] = request.FILES['icon']
            if 'is_active' in request.data:
                data['is_active'] = str(request.data.get('is_active', 'true')).lower() in ('true', '1', 'yes')
            if 'order' in request.data:
                data['order'] = int(request.data.get('order') or 0)
        else:
            data = request.data.copy()
            if 'icon' in request.FILES:
                data['icon'] = request.FILES['icon']

        serializer = CategoryUpdateSerializer(data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Категория не найдена'}, status=404)
        serializer.update(category, v)
        output = CategoryDetailSerializer(category, context={'request': request})
        return Response(output.data)

    def delete(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Категория не найдена'}, status=404)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=['Категории'],
        summary='Категории на главной',
        description=(
            'Список категорий, у которых задан `home_order` (> 0). '
            'Сортировка по возрастанию `home_order`.'
        ),
    ),
    post=extend_schema(
        tags=['Категории'],
        summary='Назначить категорию на слот главной',
        description=(
            'Устанавливает `home_order` для категории. '
            'Если другая категория уже занимала этот номер слота, у неё `home_order` сбрасывается в null.'
        ),
        request=CategoryHomeOrderAssignSerializer,
        responses={200: CategoryHomeListSerializer(many=True)},
    ),
)
class CategoryHomeListAssignView(APIView):
    """GET: home_order > 0, order_by home_order. POST: назначить слот, конфликтующие — null."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = (
            Category.objects.filter(home_order__gt=0)
            .prefetch_related('translations')
            .order_by('home_order')
        )
        serializer = CategoryHomeListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        ser = CategoryHomeOrderAssignSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        category_id = ser.validated_data['category_id']
        home_order = ser.validated_data['home_order']

        with transaction.atomic():
            try:
                category = Category.objects.select_for_update().get(pk=category_id)
            except Category.DoesNotExist:
                return Response({'category_id': ['Категория не найдена']}, status=status.HTTP_404_NOT_FOUND)

            # Bir xil home_order dagi boshqa kategoriyalarni home_order=null
            Category.objects.filter(home_order=home_order).exclude(pk=category.pk).update(home_order=None)

            category.home_order = home_order
            category.save(update_fields=['home_order', 'updated_at'])

        # Yangilangan ro'yxat (barcha home kategoriyalar)
        qs = (
            Category.objects.filter(home_order__gt=0)
            .prefetch_related('translations')
            .order_by('home_order')
        )
        out = CategoryHomeListSerializer(qs, many=True, context={'request': request})
        return Response(out.data, status=status.HTTP_200_OK)
