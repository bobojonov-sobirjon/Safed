from django.contrib import admin
from parler.admin import TranslatableAdmin
from .models import Category


@admin.register(Category)
class CategoryAdmin(TranslatableAdmin):
    list_display = ['id', 'get_name', 'parent', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['translations__name']

    def get_name(self, obj):
        return obj.safe_translation_getter('name', any_language=True) or '-'
    get_name.short_description = 'Название'
