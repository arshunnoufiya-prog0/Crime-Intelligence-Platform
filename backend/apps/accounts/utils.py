"""Accounts utils — JWT generation per spec §17.

Claims: sub, role, districts, stations, iat, exp, jti. Access 30 min,
refresh 12 h. Refresh tokens are stored HASHED (SHA-256), single-use, and
rotated on every refresh (§17). Decode always happens with
algorithms=["HS256"] — never with verify_signature disabled.
"""
from __future__ import annotations

import datetime
import hashlib
import uuid

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import RefreshToken

User = get_user_model()


def _claims(user, token_type: str, lifetime: datetime.timedelta) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        "sub": str(user.id),
        "role": user.role,
        "districts": [str(d).upper() for d in (user.districts or [])],
        "stations": [str(s).upper() for s in (user.stations or [])],
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid.uuid4().hex,
    }


def generate_tokens(user) -> tuple[str, str]:
    access = jwt.encode(
        _claims(user, "access", datetime.timedelta(minutes=settings.JWT_ACCESS_MINUTES)),
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    refresh = jwt.encode(
        _claims(user, "refresh", datetime.timedelta(hours=settings.JWT_REFRESH_HOURS)),
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    payload = jwt.decode(refresh, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    RefreshToken.objects.create(
        user=user,
        jti=payload["jti"],
        token_hash=hashlib.sha256(refresh.encode()).hexdigest(),
        expires_at=timezone.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc),
    )
    return access, refresh


def rotate_refresh(refresh_token: str) -> tuple[str, str] | None:
    """Single-use rotation (§17): validate jti + hash against the stored row,
    revoke it, issue a fresh pair. Returns None on any mismatch/reuse."""
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "refresh":
        return None
    stored = RefreshToken.objects.filter(jti=payload.get("jti"), revoked=False).first()
    if stored is None:
        return None
    if stored.token_hash != hashlib.sha256(refresh_token.encode()).hexdigest():
        return None
    if stored.expires_at <= timezone.now():
        stored.revoked = True
        stored.save(update_fields=["revoked"])
        return None
    user = User.objects.get(pk=payload.get("sub"), is_active=True)
    stored.revoked = True
    stored.save(update_fields=["revoked"])
    return generate_tokens(user)


def user_to_dict(user) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "badge_number": user.badge_number,
        "role": user.role,
        "district_id": str(user.district_id) if user.district_id else None,
        "districts": user.districts or [],
        "stations": user.stations or [],
        "is_active": user.is_active,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }
