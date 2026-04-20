"""
URL configuration for Safed project.
Includes API versioning (v1).
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_spectacular.views import (
    SpectacularAPIView, 
    SpectacularRedocView, 
    SpectacularSwaggerView
)

from config.spectacular.schema_views import custom_schema_view


# API v1 URLs
api_v1_patterns = [
    path('', include('apps.products.urls')),
    path('', include('apps.orders.urls')),
    path('', include('apps.news.urls')),
    path('', include('apps.accounts.urls')),
    path('', include('apps.categories.urls')),
    path('', include('apps.realtime.urls')),
    path('', include('apps.orders.stats_urls')),
]

urlpatterns = [
    # Admin
    # path('admin/', admin.site.urls),
    
    # API Documentation
    path('schema/', custom_schema_view, name='schema'),
    path(
        'schema-original/', 
        SpectacularAPIView.as_view(
            authentication_classes=[], 
            permission_classes=[permissions.AllowAny]
        ), 
        name='schema-original'
    ),
    path(
        'docs/', 
        SpectacularSwaggerView.as_view(
            url_name='schema', 
            authentication_classes=[], 
            permission_classes=[permissions.AllowAny]
        ), 
        name='swagger-ui'
    ),
    path(
        'redoc/', 
        SpectacularRedocView.as_view(
            url_name='schema', 
            authentication_classes=[], 
            permission_classes=[permissions.AllowAny]
        ), 
        name='redoc'
    ),
    
    # API v1 (versioned)
    path('api/v1/', include((api_v1_patterns, 'api_v1'), namespace='v1')),
]

# Static and Media files
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$", 
        serve, 
        {"document_root": settings.MEDIA_ROOT}
    ),
]
