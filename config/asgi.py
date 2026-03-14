"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from config.routing import websocket_urlpatterns
from config.middleware.tokenauth_middleware import TokenAuthMiddleware


def get_websocket_application():
    """Build WebSocket application with appropriate security."""
    websocket_app = TokenAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    )
    
    # Only use AllowedHostsOriginValidator in production
    if not settings.DEBUG:
        websocket_app = AllowedHostsOriginValidator(websocket_app)
    
    return websocket_app


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": get_websocket_application(),
})
