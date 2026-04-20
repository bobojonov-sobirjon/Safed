from django.urls import path
from . import views

urlpatterns = [
    path('orders/', views.OrderCreateView.as_view(), name='order-create'),
    path('orders/my/', views.MyOrderListView.as_view(), name='my-orders'),
    path('orders/courier/my/', views.CourierMyOrdersView.as_view(), name='courier-my-orders'),
    path('orders/active/', views.ActiveOrdersView.as_view(), name='active-orders'),
    path('orders/all/', views.OrderListView.as_view(), name='order-list'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:pk>/add-courier/', views.OrderAddCourierView.as_view(), name='order-add-courier'),
    path('orders/<int:pk>/status/', views.OrderStatusChangeView.as_view(), name='order-status'),
    path('orders/<int:pk>/finalize-pricing/', views.OrderFinalizePricingView.as_view(), name='order-finalize-pricing'),
]
