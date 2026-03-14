from django.urls import path

from .views import (
    OrderChatView,
    NotificationListView,
    UnreadNotificationListView,
    NotificationMarkReadView,
)

urlpatterns = [
    path('orders/<int:order_id>/chat/', OrderChatView.as_view(), name='order-chat'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread/', UnreadNotificationListView.as_view(), name='notification-unread'),
    path('notifications/<int:pk>/read/', NotificationMarkReadView.as_view(), name='notification-read'),
]

