from django.urls import path

from . import views


urlpatterns = [
    # Suppliers
    path('inventory/suppliers/', views.SupplierListCreateView.as_view(), name='inventory-supplier-list-create'),
    path('inventory/suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='inventory-supplier-detail'),
    path('inventory/suppliers/<int:pk>/statement/', views.SupplierStatementView.as_view(), name='inventory-supplier-statement'),

    # Receipts
    path('inventory/receipts/', views.ReceiptListCreateView.as_view(), name='inventory-receipt-list-create'),
    path('inventory/receipts/<int:pk>/', views.ReceiptDetailView.as_view(), name='inventory-receipt-detail'),
    path('inventory/receipts/<int:pk>/post/', views.ReceiptPostView.as_view(), name='inventory-receipt-post'),

    # Receipt items
    path('inventory/receipts/<int:receipt_id>/items/', views.ReceiptItemListCreateView.as_view(), name='inventory-receipt-item-list-create'),
    path('inventory/receipts/<int:receipt_id>/items/<int:item_id>/', views.ReceiptItemDetailView.as_view(), name='inventory-receipt-item-detail'),

    # Barcode lookup
    path('inventory/products/by-barcode/', views.ProductByBarcodeView.as_view(), name='inventory-product-by-barcode'),
    path(
        'inventory/products/restock/',
        views.ProductRestockByBarcodeView.as_view(),
        name='inventory-product-restock',
    ),
]

