import re
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


# Regex patterns to extract token from WebSocket paths
# /ws/chat/<room_id>/<token>/ or /ws/notifications/<token>/
TOKEN_PATTERNS = [
    re.compile(r'^ws/chat/\d+/(?P<token>[^/]+)/?$'),
    re.compile(r'^ws/notifications/(?P<token>[^/]+)/?$'),
    # ws/orders/delivery/?token=... — query; ws/orders/delivery/<jwt>/ — path
    re.compile(r'^ws/orders/delivery/token=(?P<token>.+)$'),
    re.compile(r'^ws/orders/delivery/(?P<token>[^/]+)/?$'),
]


class TokenAuthMiddleware:
    """
    ASGI middleware that reads JWT token from URL path or query string
    and attaches authenticated user to scope['user'].
    """

    def __init__(self, inner):
        self.inner = inner
        self.jwt_auth = JWTAuthentication()

    def _extract_token_from_path(self, path: str) -> str | None:
        """Extract JWT token from WebSocket path."""
        # Remove leading slash
        path = path.lstrip('/')
        
        for pattern in TOKEN_PATTERNS:
            match = pattern.match(path)
            if match:
                raw = match.group('token').strip()
                if raw.lower().startswith('token='):
                    raw = raw[6:]
                return raw or None
        return None

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        user = AnonymousUser()
        token = None

        # Try to get token from URL path
        path = scope.get('path', '')
        token = self._extract_token_from_path(path)

        # Query: ?token=...
        if not token and scope.get('query_string'):
            query_params = parse_qs(scope['query_string'].decode('utf-8'))
            tokens = query_params.get('token')
            if tokens:
                token = tokens[0]

        # Header: Authorization: Bearer <jwt> (Postman)
        if not token:
            for name, value in scope.get('headers', ()):
                if name.lower() == b'authorization':
                    raw = value.decode('utf-8', errors='ignore').strip()
                    if raw.lower().startswith('bearer '):
                        token = raw[7:].strip()
                    break

        if token:
            try:
                validated = self.jwt_auth.get_validated_token(token)
                user = await sync_to_async(self.jwt_auth.get_user)(validated)
            except InvalidToken:
                user = AnonymousUser()
            except Exception:
                user = AnonymousUser()

        scope['user'] = user

        return await self.inner(scope, receive, send)

