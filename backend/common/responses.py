"""Response envelope (spec §17, decision recorded in artifacts/backend_inventory.md).

New endpoints (api/intel/) use the spec default envelope; legacy endpoints
keep their raw shapes (frontend change-control).
"""
from __future__ import annotations

from django.http import JsonResponse


def ok(data=None, meta=None, status: int = 200) -> JsonResponse:
    payload: dict = {"ok": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return JsonResponse(payload, status=status, safe=False)


def fail(code: str, message: str, details=None, status: int = 400) -> JsonResponse:
    error: dict = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JsonResponse({"ok": False, "error": error}, status=status)
