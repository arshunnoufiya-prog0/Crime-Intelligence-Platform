"""Accounts utils — token generation and user serialization."""
from __future__ import annotations

import datetime
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


def generate_tokens(user: User) -> tuple[str, str]:
    now = datetime.datetime.now(datetime.timezone.utc)
    access_exp = now + datetime.timedelta(minutes=settings.JWT_ACCESS_MINUTES)
    refresh_exp = now + datetime.timedelta(days=settings.JWT_REFRESH_DAYS)
    access = jwt.encode(
        {"user_id": str(user.id), "type": "access", "exp": access_exp, "iat": now},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    refresh = jwt.encode(
        {"user_id": str(user.id), "type": "refresh", "exp": refresh_exp, "iat": now},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return access, refresh


def user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "badge_number": user.badge_number,
        "role": user.role,
        "district_id": str(user.district_id) if user.district_id else None,
        "is_active": user.is_active,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }