from django.contrib import admin
from .models import FIR, District, PoliceStation, Accused

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "id")
    search_fields = ("name",)

@admin.register(PoliceStation)
class PoliceStationAdmin(admin.ModelAdmin):
    list_display = ("name", "district")
    list_filter = ("district",)
    search_fields = ("name",)

@admin.register(FIR)
class FIRAdmin(admin.ModelAdmin):
    list_display = ("fir_id", "district", "police_station", "crime_head", "case_status", "case_category", "fir_registration_date")
    list_filter = ("district", "police_station", "case_status", "case_category", "crime_head")
    search_fields = ("fir_id", "crime_head", "address", "complainant_name", "gang")
    date_hierarchy = "fir_registration_date"
    readonly_fields = ("id", "created_at", "updated_at")

@admin.register(Accused)
class AccusedAdmin(admin.ModelAdmin):
    list_display = ("name", "fir", "identified")
    list_filter = ("identified",)
    search_fields = ("name", "fir__fir_id")