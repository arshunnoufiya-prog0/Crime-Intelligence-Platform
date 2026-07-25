"""Root URL configuration."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/firs/", include("apps.fir.urls")),
    path("api/llm/", include("apps.llm.urls")),
]