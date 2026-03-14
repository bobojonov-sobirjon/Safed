from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class TokenAuthMiddleware:
    """
    ASGI middleware that reads JWT token from URL path kwargs or query string
    and attaches authenticated user to scope['user'].
    """

    def __init__(self, inner):
        self.inner = inner
        self.jwt_auth = JWTAuthentication()

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        user = AnonymousUser()

        # Try to get token from URL route kwargs (e.g. /ws/.../<token>/)
        token = None
        url_route = scope.get('url_route') or {}
        kwargs = url_route.get('kwargs') or {}
        token = kwargs.get('token')

        # Fallback: query string ?token=...
        if not token and scope.get('query_string'):
            query_params = parse_qs(scope['query_string'].decode('utf-8'))
            tokens = query_params.get('token')
            if tokens:
                token = tokens[0]

        if token:
            try:
                validated = self.jwt_auth.get_validated_token(token)
                user = await sync_to_async(self.jwt_auth.get_user)(validated)
            except InvalidToken:
                user = AnonymousUser()

        scope['user'] = user

        return await self.inner(scope, receive, send)

