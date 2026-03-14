import django_filters
from .models import Category


class CategoryFilter(django_filters.FilterSet):
    """Category list uchun filterlar"""
    parent = django_filters.NumberFilter(
        field_name='parent_id',
        label='Родительская категория (ID)',
        help_text='Berilgan ID ga tegishli bolalarni qaytaradi'
    )
    category = django_filters.NumberFilter(
        field_name='parent_id',
        label='Категория ID (alias для parent)'
    )
    parent__isnull = django_filters.BooleanFilter(
        field_name='parent',
        lookup_expr='isnull',
        label='Только корневые категории'
    )
    name = django_filters.CharFilter(
        method='filter_by_name',
        label='Название',
        help_text='Har qanday tilda nom bo‘yicha qidirish'
    )

    class Meta:
        model = Category
        fields = ['parent', 'name', 'is_active']

    def filter_by_name(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(translations__name__icontains=value).distinct()
