from django.urls import path

from .views import (
    # Chat
    ChatRoomListCreateView,
    ChatRoomDetailView,
    ChatRoomByOrderView,
    ChatMessageListView,
    ChatMessageMarkReadView,
    # Notifications
    NotificationListView,
    UnreadNotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
)

urlpatterns = [
    # Chat Rooms
    path('chat/rooms/', ChatRoomListCreateView.as_view(), name='chat-room-list'),
    path('chat/rooms/<int:pk>/', ChatRoomDetailView.as_view(), name='chat-room-detail'),
    path('chat/orders/<int:order_id>/', ChatRoomByOrderView.as_view(), name='chat-by-order'),
    
    # Chat Messages (GET only - POST via WebSocket)
    path('chat/rooms/<int:room_id>/messages/', ChatMessageListView.as_view(), name='chat-messages'),
    path('chat/rooms/<int:room_id>/read/', ChatMessageMarkReadView.as_view(), name='chat-mark-read'),
    
    # Notifications
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread/', UnreadNotificationListView.as_view(), name='notification-unread'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='notification-read-all'),
    path('notifications/<int:pk>/read/', NotificationMarkReadView.as_view(), name='notification-read'),
]
