from django.urls import path

from apps.realtime import consumers


websocket_urlpatterns = [
    path('ws/chat/<int:order_id>/<str:token>/', consumers.ChatConsumer.as_asgi()),
    path('ws/notification/<str:token>/', consumers.NotificationConsumer.as_asgi()),
]

