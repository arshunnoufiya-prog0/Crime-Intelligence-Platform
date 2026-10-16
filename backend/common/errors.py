"""Typed upstream errors → machine-readable 503 (spec §0.4)."""
from __future__ import annotations

from django.http import JsonResponse


class UpstreamUnavailable(RuntimeError):
    code = "upstream_unavailable"


def upstream_503(exc: Exception) -> JsonResponse:
    code = getattr(exc, "code", "upstream_unavailable")
    return JsonResponse(
        {"ok": False, "error": {"code": code, "message": str(exc)}},
        status=503,
    )
