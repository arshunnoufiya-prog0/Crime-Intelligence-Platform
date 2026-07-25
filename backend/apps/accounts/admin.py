from django.contrib import admin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "badge_number", "role", "district", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "district")
    search_fields = ("email", "name", "badge_number")
    readonly_fields = ("date_joined", "last_login")