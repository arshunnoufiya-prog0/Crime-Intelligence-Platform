"""Accounts views — JWT auth endpoints, all JsonResponse, no DRF."""
from __future__ import annotations

import datetime
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View

from .decorators import is_authenticated, super_admin_only
from .utils import generate_tokens, user_to_dict

User = get_user_model()


@csrf_exempt
@require_http_methods(["POST"])
def login_view(request):
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"error": "invalid credentials", "code": "unauthorized"}, status=401)
    if not user.check_password(password):
        return JsonResponse({"error": "invalid credentials", "code": "unauthorized"}, status=401)
    if not user.is_active:
        return JsonResponse({"error": "account disabled", "code": "forbidden"}, status=403)
    access, refresh = generate_tokens(user)
    return JsonResponse({"access": access, "refresh": refresh, "user": user_to_dict(user)})


@csrf_exempt
@require_http_methods(["POST"])
def refresh_view(request):
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)
    refresh = data.get("refresh", "")
    try:
        payload = jwt.decode(refresh, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return JsonResponse({"error": "invalid refresh token", "code": "unauthorized"}, status=401)
    if payload.get("type") != "refresh":
        return JsonResponse({"error": "not a refresh token", "code": "bad_request"}, status=400)
    try:
        user = User.objects.get(pk=payload.get("user_id"))
    except User.DoesNotExist:
        return JsonResponse({"error": "user not found", "code": "not_found"}, status=404)
    if not user.is_active:
        return JsonResponse({"error": "account disabled", "code": "forbidden"}, status=403)
    access, new_refresh = generate_tokens(user)
    return JsonResponse({"access": access, "refresh": new_refresh})


@method_decorator(is_authenticated, name="dispatch")
class MeView(View):
    def get(self, request):
        return JsonResponse(user_to_dict(request.user))


@csrf_exempt
@require_http_methods(["POST"])
@is_authenticated
def change_password_view(request):
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)
    current = data.get("current_password", "")
    new = data.get("new_password", "")
    if not current or not new:
        return JsonResponse({"error": "both current and new password required", "code": "bad_request"}, status=400)
    user = request.user
    if not user.check_password(current):
        return JsonResponse({"error": "current password incorrect", "code": "unauthorized"}, status=401)
    user.set_password(new)
    user.save()
    return JsonResponse({"detail": "password changed"})


@method_decorator(super_admin_only, name="dispatch")
class UserListCreateView(View):
    def get(self, request):
        users = User.objects.all().order_by("-date_joined")
        return JsonResponse([user_to_dict(u) for u in users], safe=False)

    def post(self, request):
        import json
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        name = data.get("name", "")
        badge = data.get("badge_number", "")
        role = data.get("role", "READ_ONLY")
        district_id = data.get("district_id")
        if not email or not password:
            return JsonResponse({"error": "email and password required", "code": "bad_request"}, status=400)
        if User.objects.filter(email=email).exists():
            return JsonResponse({"error": "email already exists", "code": "conflict"}, status=409)
        user = User.objects.create_user(email=email, password=password, name=name, badge_number=badge, role=role)
        if district_id:
            from apps.fir.models import District
            try:
                user.district = District.objects.get(pk=district_id)
                user.save()
            except District.DoesNotExist:
                pass
        return JsonResponse(user_to_dict(user), status=201)


@method_decorator(super_admin_only, name="dispatch")
class UserDetailView(View):
    def patch(self, request, pk):
        import json
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return JsonResponse({"error": "user not found", "code": "not_found"}, status=404)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)
        for field in ("name", "badge_number", "role", "is_active"):
            if field in data:
                setattr(user, field, data[field])
        if "district_id" in data:
            from apps.fir.models import District
            try:
                user.district = District.objects.get(pk=data["district_id"]) if data["district_id"] else None
            except District.DoesNotExist:
                pass
        user.save()
        return JsonResponse(user_to_dict(user))