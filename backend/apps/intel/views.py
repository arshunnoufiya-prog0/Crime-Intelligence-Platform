"""Intel views (spec §12.5 proxy, §17 RBAC matrix).

Natural-language query: allowed for every role (scoped). Network analysis:
READ_ONLY is rejected — decorator hierarchy INVESTIGATOR+ (§17 matrix).
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.decorators import is_authenticated, investigator_or_above
from apps.audit.models import AuditEntry
from common.errors import upstream_503
from common.responses import ok

from . import proxy


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(is_authenticated, name="dispatch")
class QueryView(View):
    """POST /api/intel/query/ — SSE relay to the RAG service (§12)."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "error": {"code": "bad_request", "message": "invalid json"}},
                status=400,
            )
        question = (body.get("question") or body.get("query") or "").strip()
        if not question:
            return JsonResponse(
                {"ok": False, "error": {"code": "bad_request", "message": "question required"}},
                status=400,
            )
        conversation_id = body.get("conversation_id")
        history = body.get("history") or []
        if not isinstance(history, list):
            history = []

        def audit_sink(**facts):
            AuditEntry.objects.create(
                user_id=str(request.user.id),
                user_email=request.user.email,
                user_role=request.user.role,
                method="POST",
                path="/api/intel/query/",
                status_code=200,
                ip=request.META.get("REMOTE_ADDR"),
                payload_summary=question[:500],
                answer=(facts.get("answer") or "")[:8000],
                intent=facts.get("intent", ""),
                cypher_template_id=facts.get("cypher_template_id", ""),
                fir_ids_returned=facts.get("fir_ids_returned", []),
                prompt_token_count=facts.get("prompt_token_count", 0) or 0,
                reasoning_token_count=facts.get("reasoning_token_count", 0) or 0,
                warnings=facts.get("warnings", []),
                ttft_ms=facts.get("ttft_ms"),
                latency_ms=facts.get("latency_ms", 0) or 0,
            )

        return proxy.stream_query(request.user, question, conversation_id, history, audit_sink=audit_sink)


@method_decorator(investigator_or_above, name="dispatch")
class SubgraphView(View):
    """GET /api/intel/graph/subgraph/{fir_id}/ — evidence subgraph (§14.2 change 8 target)."""

    def get(self, request, fir_id: str):
        try:
            data = proxy.get_json(request.user, f"/v1/graph/subgraph/{fir_id}")
        except proxy.RagUpstreamError as exc:
            return upstream_503(exc)
        return ok(data)


@method_decorator(investigator_or_above, name="dispatch")
class NetworkView(View):
    """GET /api/intel/graph/network/{person_name}/ — associates + centrality (§13.1)."""

    def get(self, request, person_name: str):
        try:
            data = proxy.get_json(request.user, f"/v1/graph/network/{person_name}")
        except proxy.RagUpstreamError as exc:
            return upstream_503(exc)
        return ok(data)


@method_decorator(investigator_or_above, name="dispatch")
class ProfileView(View):
    """GET /api/intel/profile/person/{person_name}/ — grounded offender profile (§11.5)."""

    def get(self, request, person_name: str):
        try:
            data = proxy.get_json(request.user, f"/v1/profile/person/{person_name}")
        except proxy.RagUpstreamError as exc:
            return upstream_503(exc)
        return ok(data)
