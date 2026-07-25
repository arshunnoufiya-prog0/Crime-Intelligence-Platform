"""GraphQuery log model — saved on every graph query."""
from __future__ import annotations

import uuid
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

User = settings.AUTH_USER_MODEL


class GraphQuery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="graph_queries")
    query = models.TextField()
    intent = models.CharField(max_length=64, blank=True)
    fir_ids = models.JSONField(default=list)
    latency_ms = models.PositiveIntegerField(default=0)
    confidence = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "llm_graphquery"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user} - {self.query[:50]}"


@receiver(post_save, sender=GraphQuery)
def graph_query_audit(sender, instance: GraphQuery, created, **kwargs):
    if not created:
        return
    # Signal the audit app — we create an AuditEntry here without modifying audit app
    from apps.audit.models import AuditEntry
    AuditEntry.objects.create(
        user_email=instance.user.email,
        user_role=instance.user.role,
        method="POST",
        path="/api/llm/graph/query/",
        status_code=200,
        ip="",  # not available in signal
        payload_summary=f"graph_query:{instance.query[:200]}",
    )