"""
Reusable mixins for views and serializers.
"""
from typing import Optional, Type
from rest_framework.request import Request
from django.db.models import Model


class AuditMixin:
    """Mixin to automatically set audit fields on create/update."""
    
    def perform_create(self, serializer):
        """Set created_by on create."""
        user = self._get_current_user()
        if user and hasattr(serializer.Meta.model, 'created_by'):
            serializer.save(created_by=user)
        else:
            serializer.save()
    
    def perform_update(self, serializer):
        """Set updated_by on update."""
        user = self._get_current_user()
        if user and hasattr(serializer.Meta.model, 'updated_by'):
            serializer.save(updated_by=user)
        else:
            serializer.save()
    
    def _get_current_user(self):
        request = getattr(self, 'request', None)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return request.user
        return None


class CacheMixin:
    """Mixin for cache operations."""
    
    cache_timeout: int = 300  # 5 minutes default
    cache_key_prefix: str = ''
    
    def get_cache_key(self, *args) -> str:
        """Generate cache key."""
        parts = [self.cache_key_prefix] + [str(arg) for arg in args]
        return ':'.join(filter(None, parts))


class OptimizedQueryMixin:
    """Mixin for optimized querysets with select_related and prefetch_related."""
    
    select_related_fields: tuple = ()
    prefetch_related_fields: tuple = ()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if self.select_related_fields:
            queryset = queryset.select_related(*self.select_related_fields)
        
        if self.prefetch_related_fields:
            queryset = queryset.prefetch_related(*self.prefetch_related_fields)
        
        return queryset
