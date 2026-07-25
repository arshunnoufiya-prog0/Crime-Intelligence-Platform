"""Audit models + middleware — AuditEntry logs every mutating request."""
from __future__ import annotations

import json
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class AuditEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_email = models.EmailField(blank=True, default="")
    user_role = models.CharField(max_length=20, blank=True, default="")
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.IntegerField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    payload_summary = models.TextField(blank=True, default="")  # first 500 chars of request body

    class Meta:
        db_table = "audit_entry"
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["user_email"]),
            models.Index(fields=["path"]),
        ]

    def __str__(self):
        return f"{self.method} {self.path} -> {self.status_code} ({self.user_email})"


class RequestAuditMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.path.startswith("/admin/"):
            try:
                user = getattr(request, "user", None)
                email = user.email if user and user.is_authenticated else ""
                role = user.role if user and user.is_authenticated else ""
                body = ""
                if hasattr(request, "body") and request.body:
                    try:
                        body = request.body.decode("utf-8")[:500]
                    except Exception:
                        body = "<binary>"
                ip = request.META.get("REMOTE_ADDR") or request.META.get("HTTP_X_FORWARDED_FOR")
                AuditEntry.objects.create(
                    user_email=email,
                    user_role=role,
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    ip=ip,
                    payload_summary=body,
                )
            except Exception:
                pass  # never break the response
        return response