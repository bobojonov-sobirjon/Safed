"""DRF authentication helpers."""
from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class OptionalJWTAuthentication(JWTAuthentication):
    """
    Public catalog endpoints: no token → guest; valid token → user;
    invalid/expired token → guest (not 401).
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError):
            return None
