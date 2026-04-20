from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, PhoneOTP


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ['id', 'phone', 'first_name', 'last_name', 'groups_display', 'is_admin', 'is_active', 'created_at']
    list_filter = ['is_admin', 'is_active', 'is_verified']
    search_fields = ['phone', 'first_name', 'last_name']
    ordering = ['-created_at']

    @admin.display(description='Groups')
    def groups_display(self, obj):
        return ', '.join(obj.groups.values_list('name', flat=True))


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ['id', 'phone', 'code', 'is_verified', 'created_at']
    list_filter = ['is_verified']
