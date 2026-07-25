from django.contrib import admin
from .models import AuditEntry

@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "method", "path", "status_code", "user_email", "user_role")
    list_filter = ("method", "status_code", "user_role")
    search_fields = ("user_email", "path", "payload_summary")
    readonly_fields = ("timestamp", "method", "path", "status_code", "user_email", "user_role", "ip", "payload_summary")
    ordering = ("-timestamp",)