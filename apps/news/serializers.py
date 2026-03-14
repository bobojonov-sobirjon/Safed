from rest_framework import serializers
from django.conf import settings
from parler.utils.context import switch_language

from .models import Posts, PostImages


_REQUIRED = {'required': 'Обязательное поле.'}
_LANGS = [c['code'] for c in settings.PARLER_LANGUAGES[None]]


class PostImageSerializer(serializers.ModelSerializer):
    """Сериализатор для изображений поста"""

    class Meta:
        model = PostImages
        fields = ['id', 'post', 'image', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_post(self, value):
        if value and not Posts.objects.filter(pk=value.pk).exists():
            raise serializers.ValidationError('Пост не найден')
        return value


class PostImageCreateSerializer(serializers.Serializer):
    """Создание изображения (form-data)"""
    post = serializers.IntegerField(required=True, error_messages=_REQUIRED)
    image = serializers.ImageField(required=True, error_messages=_REQUIRED)

    def validate_post(self, value):
        if not Posts.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Пост не найден')
        return value


class PostImageUpdateSerializer(serializers.Serializer):
    """Обновление изображения"""
    post = serializers.IntegerField(required=False)
    image = serializers.ImageField(required=False)

    def validate_post(self, value):
        if value is not None and not Posts.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Пост не найден')
        return value


class TranslationItemSerializer(serializers.Serializer):
    """Вложенная структура для одного языка"""
    title = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)


class PostCreateSerializer(serializers.Serializer):
    """Создание поста. translations: { uz: {title, content}, ru: {...}, en: {...} }. images - внутри запроса."""
    translations = serializers.DictField(
        child=TranslationItemSerializer(),
        required=True,
        error_messages={'required': 'Обязательное поле.'}
    )
    is_active = serializers.BooleanField(required=False, default=True)


class PostUpdateSerializer(serializers.Serializer):
    """Обновление поста. translations: { uz: {title, content}, ru: {...}, en: {...} }"""
    translations = serializers.DictField(
        child=TranslationItemSerializer(),
        required=False
    )
    is_active = serializers.BooleanField(required=False)


class PostListSerializer(serializers.ModelSerializer):
    """Список постов. translations: { uz: {title, content}, ru: {...}, en: {...} }"""
    images = PostImageSerializer(many=True, read_only=True)
    translations = serializers.SerializerMethodField()

    class Meta:
        model = Posts
        fields = ['id', 'translations', 'is_active', 'created_at', 'updated_at', 'images']

    def get_translations(self, obj):
        result = {}
        for lang in _LANGS:
            if obj.has_translation(lang):
                with switch_language(obj, lang):
                    result[lang] = {
                        'title': obj.title or '',
                        'content': obj.content or '',
                    }
        return result


class PostDetailSerializer(PostListSerializer):
    """Детальный пост (тот же что и список)"""
    pass
