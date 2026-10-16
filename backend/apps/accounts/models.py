"""Accounts models — CustomUser with RBAC roles."""
from __future__ import annotations

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", _("Super Admin")
    ANALYST = "ANALYST", _("Analyst")
    INVESTIGATOR = "INVESTIGATOR", _("Investigator")
    READ_ONLY = "READ_ONLY", _("Read Only")


class CustomUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError(_("Email is required"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.SUPER_ADMIN)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    name = models.CharField(_("name"), max_length=150, blank=True)
    badge_number = models.CharField(_("badge number"), max_length=50, blank=True)
    district = models.ForeignKey(
        "fir.District",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="officers",
    )
    # RBAC scope (spec §17): districts[] and stations[] carried in the JWT
    # claims and injected into every RAG request (§14.3 change 3). Values are
    # uppercase codes, e.g. ["BENGALURU_URBAN"] / ["JAYANAGAR_PS"].
    districts = models.JSONField(default=list, blank=True)
    stations = models.JSONField(default=list, blank=True)
    role = models.CharField(_("role"), max_length=20, choices=Role.choices, default=Role.READ_ONLY)
    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "badge_number"]

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self) -> str:
        return self.email


class RefreshToken(models.Model):
    """Hashed, single-use, rotating refresh tokens (spec §17).

    The raw refresh token is NEVER stored — only its SHA-256 hash. On every
    refresh the old row is revoked and a new pair is issued.
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="refresh_tokens")
    jti = models.CharField(max_length=64, unique=True)
    token_hash = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_refreshtoken"
        indexes = [
            models.Index(fields=["user", "revoked"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"refresh:{self.jti[:8]}… user={self.user_id}"