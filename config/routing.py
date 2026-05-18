from django.urls import re_path

from apps.realtime import consumers
from apps.realtime import delivery_consumer


websocket_urlpatterns = [
    re_path(r'^ws/chat/(?P<room_id>\d+)/(?P<token>[^/]+)/?$', consumers.ChatConsumer.as_asgi()),
    re_path(r'^ws/notifications/(?P<token>[^/]+)/?$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'^ws/orders/delivery/?$', delivery_consumer.OrderDeliveryConsumer.as_asgi()),
  # Postman: ws/.../delivery/token=<jwt>  (not ?token=)
    re_path(r'^ws/orders/delivery/token=(?P<token>.+)$', delivery_consumer.OrderDeliveryConsumer.as_asgi()),
    re_path(r'^ws/orders/delivery/(?P<token>[^/]+)/?$', delivery_consumer.OrderDeliveryConsumer.as_asgi()),
]

