from django.urls import path
from . import views
from . import checkout_views
from . import click_views
from . import picking_views
from . import cash_views

urlpatterns = [
    path('checkout/pricing-preview/', checkout_views.OrderPricingPreviewView.as_view(), name='pricing-preview'),
    # Delivery slots (asosiy). busy-slots — xuddi shu view (eski nom, bitta tizim).
    path('checkout/delivery-slots/', checkout_views.DeliverySlotAvailabilityView.as_view(), name='delivery-slots'),
    path('busy-slots/', checkout_views.DeliverySlotAvailabilityView.as_view(), name='busy-slots'),
    path('addresses/', checkout_views.DeliveryAddressListCreateView.as_view(), name='delivery-address-list'),
    path('addresses/<int:pk>/', checkout_views.DeliveryAddressDetailView.as_view(), name='delivery-address-detail'),

    path('orders/', views.OrderCreateView.as_view(), name='order-create'),    path('orders/cancel-reasons/', checkout_views.OrderCancelReasonListView.as_view(), name='order-cancel-reasons'),
    path('orders/cash/confirm/', cash_views.CashDeliveryConfirmView.as_view(), name='cash-delivery-confirm'),
    path('orders/my/', views.MyOrderListView.as_view(), name='my-orders'),
    path('orders/<int:pk>/cash-qr-image/', cash_views.CashQrImageView.as_view(), name='order-cash-qr-image'),
    path(
        'orders/<int:pk>/delivery-response/',
        cash_views.CustomerDeliveryResponseView.as_view(),
        name='order-delivery-response',
    ),
    path('orders/courier/my/', views.CourierMyOrdersView.as_view(), name='courier-my-orders'),
    path('orders/active/', views.ActiveOrdersView.as_view(), name='active-orders'),
    path('orders/all/', views.OrderListView.as_view(), name='order-list'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:pk>/add-courier/', views.OrderAddCourierView.as_view(), name='order-add-courier'),
    path('orders/<int:pk>/status/', views.OrderStatusChangeView.as_view(), name='order-status'),
    path('orders/<int:pk>/cancel/', checkout_views.OrderUserCancelView.as_view(), name='order-user-cancel'),
    path('orders/<int:pk>/click-payment/', click_views.OrderClickPaymentView.as_view(), name='order-click-payment'),
    path(
        'orders/<int:pk>/picking-lines/<int:line_id>/',
        picking_views.OrderPickingLineUpdateView.as_view(),
        name='order-picking-line',
    ),
    path('orders/<int:pk>/picking/scan/', picking_views.OrderPickingScanView.as_view(), name='order-picking-scan'),

    path('payments/click/prepare/', click_views.ClickPrepareView.as_view(), name='click-prepare'),
    path('payments/click/complete/', click_views.ClickCompleteView.as_view(), name='click-complete'),

    # Admin Fees (API, for Super Admin/Admin)
    path('admin/fees/settings/', views.OrderFeeSettingsView.as_view(), name='order-fee-settings'),
    path('admin/fees/delivery-rules/', views.DeliveryFeeRuleListCreateView.as_view(), name='delivery-fee-rule-list-create'),
    path('admin/fees/delivery-rules/<int:pk>/', views.DeliveryFeeRuleDetailView.as_view(), name='delivery-fee-rule-detail'),
    path('admin/delivery-zones/', views.DeliveryZoneListCreateView.as_view(), name='delivery-zone-list-create'),
    path('admin/delivery-zones/<int:pk>/', views.DeliveryZoneDetailView.as_view(), name='delivery-zone-detail'),
    path('admin/cashback/settings/', views.CashbackSettingsView.as_view(), name='cashback-settings'),
    path('admin/cashback/transactions/', views.CashbackTransactionListView.as_view(), name='cashback-transactions'),
    path('checkout/delivery-zone/check/', checkout_views.DeliveryZoneCheckView.as_view(), name='delivery-zone-check'),
    path('users/me/cashback/', checkout_views.UserCashbackView.as_view(), name='user-cashback'),
    path('users/me/cashback/history/', checkout_views.UserCashbackHistoryView.as_view(), name='user-cashback-history'),
]
