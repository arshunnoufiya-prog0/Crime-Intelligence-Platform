"""Root URL configuration (spec §4, §14.3 change 4).

/api/llm/* endpoints are REMOVED — they spoke to the old Graph-RAG service.
/api/intel/* replaces them (§14.3 change 1). /api/health/ serves the compose
healthcheck (§16).
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/firs/", include("apps.fir.urls")),
    path("api/intel/", include("apps.intel.urls")),
]
