"""RBAC decorators — is_authenticated, require_role, and role aliases."""
from __future__ import annotations

from functools import wraps
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

# Role hierarchy (cumulative)
ROLE_HIERARCHY = {
    "SUPER_ADMIN": {"SUPER_ADMIN", "ANALYST", "INVESTIGATOR", "READ_ONLY"},
    "ANALYST": {"ANALYST", "INVESTIGATOR", "READ_ONLY"},
    "INVESTIGATOR": {"INVESTIGATOR", "READ_ONLY"},
    "READ_ONLY": {"READ_ONLY"},
}


def _has_role(user, required: set[str]) -> bool:
    return user and user.is_active and user.role in required


def is_authenticated(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_active:
            return JsonResponse({"error": "authentication required", "code": "unauthorized"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_role(*roles: str):
    required = set()
    for r in roles:
        required.update(ROLE_HIERARCHY.get(r, {r}))

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not _has_role(request.user, required):
                return JsonResponse({"error": "insufficient permissions", "code": "forbidden"}, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Aliases
login_required = is_authenticated
super_admin_only = require_role("SUPER_ADMIN")
analyst_or_above = require_role("ANALYST")
investigator_or_above = require_role("INVESTIGATOR")