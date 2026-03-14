from django.urls import re_path

from apps.realtime import consumers


websocket_urlpatterns = [
    re_path(r'^ws/chat/(?P<room_id>\d+)/(?P<token>[^/]+)/?$', consumers.ChatConsumer.as_asgi()),
    re_path(r'^ws/notifications/(?P<token>[^/]+)/?$', consumers.NotificationConsumer.as_asgi()),
]

