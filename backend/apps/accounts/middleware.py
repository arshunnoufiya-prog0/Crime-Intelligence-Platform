"""JWT authentication middleware — reads Authorization: Bearer <token>, decodes with PyJWT."""
from __future__ import annotations

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin

User = get_user_model()


class JWTAuthMiddleware(MiddlewareMixin):
    def process_request(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth[7:].strip()
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        except jwt.PyJWTError:
            request.user = None
            return None
        try:
            user = User.objects.get(pk=payload.get("sub"))
        except User.DoesNotExist:
            request.user = None
            return None
        if not user.is_active:
            request.user = None
            return None
        request.user = user
        return None