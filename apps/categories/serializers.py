from rest_framework import serializers
from .models import Category


PARLER_LANGUAGES = ['uz', 'ru', 'en']


def get_category_translations(obj):
    """Barcha tillar uchun tarjimalarni olish"""
    result = {}
    for lang in PARLER_LANGUAGES:
        if obj.has_translation(lang):
            obj.set_current_language(lang)
            result[lang] = {'name': obj.name or ''}
    return result


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Ierarxik qatorli category serializer (GET uchun)"""
    name = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()
    child_category = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'icon', 'is_active', 'order', 'child_category']

    def get_name(self, obj):
        translations = {}
        for lang in PARLER_LANGUAGES:
            if obj.has_translation(lang):
                obj.set_current_language(lang)
                translations[lang] = {'name': obj.name or ''}
        return translations

    def get_icon(self, obj):
        if obj.icon:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.icon.url)
            return obj.icon.url
        return None

    def get_child_category(self, obj):
        children = obj.children.all().order_by('order')
        return CategoryTreeSerializer(children, many=True, context=self.context).data


class CategoryDetailSerializer(serializers.ModelSerializer):
    """Bitta category uchun to'liq ma'lumot (GET by id)"""
    name = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), allow_null=True, required=False)
    child_category = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'icon', 'is_active', 'order', 'parent', 'child_category', 'created_at', 'updated_at']

    def get_name(self, obj):
        return get_category_translations(obj)

    def get_icon(self, obj):
        if obj.icon:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.icon.url)
            return obj.icon.url
        return None

    def get_child_category(self, obj):
        children = obj.children.all().order_by('order')
        return CategoryTreeSerializer(children, many=True, context=self.context).data


# ========== POST/PUT uchun serializers ==========

_REQUIRED = {'required': 'Обязательное поле.'}

class CategoryCreateSerializer(serializers.Serializer):
    """Root category yaratish - FormData (icon bilan)"""
    translations = serializers.JSONField(required=True, help_text='{"uz": {"name": "..."}, "ru": {"name": "..."}, "en": {"name": "..."}}', error_messages=_REQUIRED)
    icon = serializers.ImageField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    order = serializers.IntegerField(default=0)

    def validate_translations(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("translations должен быть объектом")
        for lang, data in value.items():
            if lang not in PARLER_LANGUAGES:
                raise serializers.ValidationError(f"Неверный код языка: {lang}")
            if not isinstance(data, dict) or 'name' not in data:
                raise serializers.ValidationError(f"Для {lang} обязательно поле 'name'")
        return value

    def create(self, validated_data):
        translations = validated_data.pop('translations')
        icon = validated_data.pop('icon', None)
        category = Category.objects.create(
            icon=icon,
            is_active=validated_data.get('is_active', True),
            order=validated_data.get('order', 0),
        )
        for lang, data in translations.items():
            category.create_translation(lang, name=data.get('name', ''))
        return category


class ChildCategoryCreateSerializer(serializers.Serializer):
    """Child category yaratish - FormData (icon bilan)"""
    parent = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=True, error_messages={'required': 'Обязательное поле.', 'does_not_exist': 'Категория не найдена.'})
    translations = serializers.JSONField(required=True, error_messages=_REQUIRED)
    icon = serializers.ImageField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    order = serializers.IntegerField(default=0)

    def validate_translations(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("translations должен быть объектом")
        for lang, data in value.items():
            if lang not in PARLER_LANGUAGES:
                raise serializers.ValidationError(f"Неверный код языка: {lang}")
            if not isinstance(data, dict) or 'name' not in data:
                raise serializers.ValidationError(f"Для {lang} обязательно поле 'name'")
        return value

    def create(self, validated_data):
        parent = validated_data.pop('parent')
        translations = validated_data.pop('translations')
        icon = validated_data.pop('icon', None)
        category = Category.objects.create(
            parent=parent,
            icon=icon,
            is_active=validated_data.get('is_active', True),
            order=validated_data.get('order', 0),
        )
        for lang, data in translations.items():
            category.create_translation(lang, name=data.get('name', ''))
        return category


class CategoryUpdateSerializer(serializers.Serializer):
    """Category yangilash - qisman translations (faqat yuborilgan tillar o'zgaradi)"""
    translations = serializers.JSONField(required=False)
    icon = serializers.ImageField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    order = serializers.IntegerField(required=False)

    def validate_translations(self, value):
        if value is None:
            return value
        if not isinstance(value, dict):
            raise serializers.ValidationError("translations должен быть объектом")
        for lang, data in value.items():
            if lang not in PARLER_LANGUAGES:
                raise serializers.ValidationError(f"Неверный код языка: {lang}")
            if not isinstance(data, dict) or 'name' not in data:
                raise serializers.ValidationError(f"Для {lang} обязательно поле 'name'")
        return value

    def update(self, instance, validated_data):
        translations = validated_data.pop('translations', None)
        if 'icon' in validated_data:
            instance.icon = validated_data.get('icon', instance.icon)
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']
        if 'order' in validated_data:
            instance.order = validated_data['order']
        instance.save()

        if translations:
            for lang, data in translations.items():
                name = data.get('name', '')
                if instance.has_translation(lang):
                    instance.set_current_language(lang)
                    instance.name = name
                    instance.save()
                else:
                    instance.create_translation(lang, name=name)
        return instance
