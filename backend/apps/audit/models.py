"""Audit models (spec §14.3 change 2, §17).

APPEND-ONLY: no update or delete view exists anywhere for AuditEntry, and
none may be added. The audit row for a streamed query stores the ANSWER text
and the reasoning TOKEN COUNT — the reasoning text itself is NEVER stored
(model deliberation is not a record, §1.3 rule 2).

The request-audit middleware lives in apps/audit/middleware.py.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class AuditEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.CharField(max_length=64, blank=True, default="")
    user_email = models.EmailField(blank=True, default="")
    user_role = models.CharField(max_length=20, blank=True, default="")
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.IntegerField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    payload_summary = models.TextField(blank=True, default="")

    answer = models.TextField(blank=True, default="")
    intent = models.CharField(max_length=40, blank=True, default="")
    cypher_template_id = models.CharField(max_length=40, blank=True, default="")
    fir_ids_returned = models.JSONField(default=list, blank=True)
    prompt_token_count = models.IntegerField(default=0)
    reasoning_token_count = models.IntegerField(default=0)
    warnings = models.JSONField(default=list, blank=True)
    ttft_ms = models.IntegerField(null=True, blank=True)
    latency_ms = models.IntegerField(default=0)

    class Meta:
        db_table = "audit_entry"
        indexes = [
            models.Index(fields=["user_id", "timestamp"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["user_email"]),
            models.Index(fields=["path"]),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.path} -> {self.status_code} ({self.user_email})"
