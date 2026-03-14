from django.urls import path
from . import views

urlpatterns = [
    # Badge
    path('badges/', views.BadgeListCreateView.as_view(), name='badge-list-create'),
    path('badges/<int:pk>/', views.BadgeDetailView.as_view(), name='badge-detail'),

    # Unit
    path('units/', views.UnitListCreateView.as_view(), name='unit-list-create'),
    path('units/<int:pk>/', views.UnitDetailView.as_view(), name='unit-detail'),

    # Product
    path('products/', views.ProductListCreateView.as_view(), name='product-list-create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),

    # ProductBarcode
    path('product-barcodes/<int:pk>/', views.ProductBarcodeDetailView.as_view(), name='product-barcode-detail'),

    # ProductImage
    path('product-images/<int:pk>/', views.ProductImageDetailView.as_view(), name='product-image-detail'),

    # ProductSavedUser
    path('saved/', views.ProductSavedListCreateView.as_view(), name='saved-list-create'),
    path('saved/<int:product_id>/', views.ProductSavedDeleteView.as_view(), name='saved-delete'),
]
