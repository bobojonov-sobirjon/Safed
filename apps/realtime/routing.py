from django.urls import path

from . import consumers

websocket_urlpatterns = [
    # Chat WebSocket - connect to a specific chat room
    path('ws/chat/<int:room_id>/<str:token>/', consumers.ChatConsumer.as_asgi()),
    
    # Notification WebSocket - receive real-time notifications
    path('ws/notifications/<str:token>/', consumers.NotificationConsumer.as_asgi()),
]
