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