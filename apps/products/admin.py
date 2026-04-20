from django.contrib import admin
from parler.admin import TranslatableAdmin

from .models import Products, ProductImage, ProductBarcode, Badge, Unit


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ['created_at', 'updated_at']


class ProductBarcodeInline(admin.TabularInline):
    model = ProductBarcode
    extra = 0
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Products)
class ProductsAdmin(TranslatableAdmin):
    list_display = ['id', 'safe_name', 'category', 'shelf_location', 'price', 'quantity', 'is_active', 'created_at']
    list_filter = ['is_active', 'category']
    search_fields = ['unique_id', 'shelf_location', 'translations__name', 'barcodes__barcode']
    ordering = ['-created_at']
    inlines = [ProductImageInline, ProductBarcodeInline]

    def safe_name(self, obj):
        return obj.safe_translation_getter('name', any_language=True) or '-'


@admin.register(Badge)
class BadgeAdmin(TranslatableAdmin):
    list_display = ['id', 'safe_name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['translations__name']
    ordering = ['-created_at']

    def safe_name(self, obj):
        return obj.safe_translation_getter('name', any_language=True) or '-'


@admin.register(Unit)
class UnitAdmin(TranslatableAdmin):
    list_display = ['id', 'safe_name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['translations__name']
    ordering = ['-created_at']

    def safe_name(self, obj):
        return obj.safe_translation_getter('name', any_language=True) or '-'

from django.contrib import admin

# Register your models here.
