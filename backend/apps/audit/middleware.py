"""Request audit middleware (spec §17: audit is append-only).

Logs every mutating request. Streamed-query specifics (intent, citations,
token counts, warnings, TTFT) are written by the intel proxy's audit_sink
into the same append-only AuditEntry model.
"""
from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin

from .models import AuditEntry


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
                    except Exception:  # noqa: BLE001 — binary payloads are summarized, never fatal
                        body = "<binary>"
                ip = request.META.get("REMOTE_ADDR") or request.META.get("HTTP_X_FORWARDED_FOR")
                AuditEntry.objects.create(
                    user_id=str(user.id) if user and user.is_authenticated else "",
                    user_email=email,
                    user_role=role,
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    ip=ip,
                    payload_summary=body,
                )
            except Exception:  # noqa: BLE001 — auditing must never break the response
                pass
        return response
