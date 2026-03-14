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
from channels.sessions import SessionMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from config.routing import websocket_urlpatterns
from config.middleware.tokenauth_middleware import TokenAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        SessionMiddlewareStack(
            AuthMiddlewareStack(
                TokenAuthMiddleware(
                    URLRouter(websocket_urlpatterns)
                )
            )
        )
    ),
})
