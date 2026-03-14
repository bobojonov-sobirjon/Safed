import json
from django.http import QueryDict
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Posts, PostImages
from .serializers import (
    PostListSerializer,
    PostDetailSerializer,
    PostCreateSerializer,
    PostUpdateSerializer,
    PostImageSerializer,
    PostImageCreateSerializer,
    PostImageUpdateSerializer,
)


# ========== Posts ==========

@extend_schema(
    tags=['Посты'],
    summary='Список постов',
    description='Фильтрация по дате (created_at) и is_active.',
    parameters=[
        OpenApiParameter(name='date_from', type=OpenApiTypes.DATE, description='Дата от (YYYY-MM-DD)'),
        OpenApiParameter(name='date_to', type=OpenApiTypes.DATE, description='Дата до (YYYY-MM-DD)'),
        OpenApiParameter(name='is_active', type=OpenApiTypes.BOOL, description='Фильтр по активности'),
    ],
)
class PostListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        date_from = request.query_params.get('date_from', '').strip()
        date_to = request.query_params.get('date_to', '').strip()
        is_active = request.query_params.get('is_active')

        queryset = Posts.objects.all().order_by('-created_at')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        if is_active is not None:
            val = str(is_active).lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_active=val)

        data = PostListSerializer(queryset, many=True, context={'request': request}).data
        return Response(data)


@extend_schema(
    tags=['Посты'],
    summary='Получить пост по ID',
)
class PostDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            post = Posts.objects.get(pk=pk)
        except Posts.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PostDetailSerializer(post, context={'request': request}).data)


def _parse_request_data(request):
    """Парсинг данных из JSON или form-data (translations как JSON-строка)"""
    data = request.data
    if isinstance(data, QueryDict):
        result = {}
        for key in data.keys():
            if key != 'images':
                result[key] = data.get(key)
        if result.get('is_active') == 'false':
            result['is_active'] = False
        elif result.get('is_active') == 'true':
            result['is_active'] = True
        if 'translations' in result and isinstance(result['translations'], str):
            try:
                result['translations'] = json.loads(result['translations'])
            except json.JSONDecodeError:
                pass
        return result
    return data


@extend_schema(
    tags=['Посты'],
    summary='Создать пост',
    description='''Создание нового поста с переводами.

**Поля:**
- `translations` - JSON-строка с переводами (обязательно)
- `is_active` - активен ли пост (опционально, по умолчанию true)
- `images` - изображения поста (опционально)

**Структура translations:**
```json
{
  "uz": {"title": "Sarlavha", "content": "Matn"},
  "ru": {"title": "Заголовок", "content": "Текст"},
  "en": {"title": "Title", "content": "Content"}
}
```
''',
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'translations': {
                    'type': 'string',
                    'description': 'JSON-строка с переводами',
                    'example': '{"uz": {"title": "Yangilik", "content": "Matn"}, "ru": {"title": "Новость", "content": "Текст"}, "en": {"title": "News", "content": "Content"}}',
                },
                'is_active': {'type': 'boolean', 'default': True, 'example': True},
                'images': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'}, 'description': 'Изображения'},
            },
            'required': ['translations'],
        }
    },
)
class PostCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_request_data(request)
        serializer = PostCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v = serializer.validated_data
        files = list(request.FILES.getlist('images')) if request.FILES else []

        post = Posts()
        post.is_active = v.get('is_active', True)
        post.save()
        translations = v.get('translations') or {}
        for lang, trans in translations.items():
            if isinstance(trans, dict) and lang in ('ru', 'uz', 'en'):
                post.set_current_language(lang)
                if 'title' in trans:
                    post.title = trans.get('title', '')
                if 'content' in trans:
                    post.content = trans.get('content', '')
        post.save()
        for img in files:
            PostImages.objects.create(post=post, image=img)
        return Response(PostDetailSerializer(post, context={'request': request}).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Посты'],
    summary='Обновить пост',
    description='''Обновление поста. Все поля опциональны.

**Структура translations:**
```json
{
  "uz": {"title": "Yangi sarlavha", "content": "Yangi matn"},
  "ru": {"title": "Новый заголовок", "content": "Новый текст"},
  "en": {"title": "New title", "content": "New content"}
}
```
''',
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'translations': {
                    'type': 'string',
                    'description': 'JSON-строка с переводами',
                    'example': '{"uz": {"title": "Yangi sarlavha"}, "ru": {"title": "Новый заголовок"}}',
                },
                'is_active': {'type': 'boolean', 'example': True},
            },
        }
    },
)
class PostUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        data = _parse_request_data(request)
        serializer = PostUpdateSerializer(data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data

        try:
            post = Posts.objects.get(pk=pk)
        except Posts.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if 'is_active' in v:
            post.is_active = v['is_active']
        translations = v.get('translations') or {}
        for lang, trans in translations.items():
            if isinstance(trans, dict) and lang in ('ru', 'uz', 'en'):
                post.set_current_language(lang)
                if 'title' in trans:
                    post.title = trans.get('title', '')
                if 'content' in trans:
                    post.content = trans.get('content', '')
        post.save()
        return Response(PostDetailSerializer(post, context={'request': request}).data)


@extend_schema(tags=['Посты'], summary='Удалить пост')
class PostDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            post = Posts.objects.get(pk=pk)
        except Posts.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== PostImages ==========

@extend_schema(
    tags=['Изображения постов'],
    summary='Список изображений постов',
    parameters=[
        OpenApiParameter(name='post', type=OpenApiTypes.INT, description='ID поста'),
    ],
)
class PostImageListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        post_id = request.query_params.get('post')
        if post_id:
            queryset = PostImages.objects.filter(post_id=post_id).order_by('-created_at')
        else:
            queryset = PostImages.objects.all().order_by('-created_at')
        return Response(PostImageSerializer(queryset, many=True, context={'request': request}).data)


@extend_schema(tags=['Изображения постов'], summary='Получить изображение по ID')
class PostImageDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            img = PostImages.objects.get(pk=pk)
        except PostImages.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PostImageSerializer(img, context={'request': request}).data)


@extend_schema(
    tags=['Изображения постов'],
    summary='Добавить изображения к посту',
    description='''Добавление изображений к существующему посту.

**Поля:**
- `post` - ID поста (обязательно)
- `images` - файлы изображений (обязательно)
''',
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'post': {'type': 'integer', 'description': 'ID поста', 'example': 1},
                'images': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'}, 'description': 'Изображения'},
            },
            'required': ['post', 'images'],
        }
    },
)
class PostImageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        post_id = request.data.get('post')
        if not post_id:
            return Response({'post': ['Обязательное поле.']}, status=status.HTTP_400_BAD_REQUEST)

        files = list(request.FILES.getlist('images')) or list(request.FILES.getlist('image'))
        if not files:
            return Response({'image': ['Обязательное поле.']}, status=status.HTTP_400_BAD_REQUEST)

        try:
            post = Posts.objects.get(pk=post_id)
        except Posts.DoesNotExist:
            return Response({'post': ['Пост не найден']}, status=status.HTTP_400_BAD_REQUEST)

        created = [PostImages.objects.create(post=post, image=f) for f in files]
        return Response(PostImageSerializer(created, many=True, context={'request': request}).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Изображения постов'],
    summary='Обновить изображение',
    description='Замена изображения поста.',
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'image': {'type': 'string', 'format': 'binary', 'description': 'Новое изображение'},
            },
            'required': ['image'],
        }
    },
)
class PostImageUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            img = PostImages.objects.get(pk=pk)
        except PostImages.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not request.FILES.get('image'):
            return Response({'image': ['Обязательное поле.']}, status=status.HTTP_400_BAD_REQUEST)

        img.image = request.FILES['image']
        img.save()
        return Response(PostImageSerializer(img, context={'request': request}).data)


@extend_schema(tags=['Изображения постов'], summary='Удалить изображение')
class PostImageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            img = PostImages.objects.get(pk=pk)
        except PostImages.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        img.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
