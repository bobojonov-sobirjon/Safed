from django.urls import path, re_path

from . import consumers
from . import delivery_consumer

websocket_urlpatterns = [
    path('ws/chat/<int:room_id>/<str:token>/', consumers.ChatConsumer.as_asgi()),
    path('ws/notifications/<str:token>/', consumers.NotificationConsumer.as_asgi()),
    path('ws/orders/delivery/', delivery_consumer.OrderDeliveryConsumer.as_asgi()),
    re_path(r'^ws/orders/delivery/token=(?P<token>.+)$', delivery_consumer.OrderDeliveryConsumer.as_asgi()),
    path('ws/orders/delivery/<str:token>/', delivery_consumer.OrderDeliveryConsumer.as_asgi()),
]
