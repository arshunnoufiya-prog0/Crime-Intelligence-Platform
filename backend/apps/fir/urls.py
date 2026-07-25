from django.urls import path
from . import views

# NOTE: stats/ MUST come before <uuid:pk>/ to avoid collision
urlpatterns = [
    path("", views.fir_list, name="fir_list"),
    path("stats/", views.fir_stats, name="fir_stats"),
    path("districts/", views.districts_list, name="districts_list"),
    path("stations/", views.stations_list, name="stations_list"),
    path("<uuid:pk>/", views.fir_detail, name="fir_detail"),
    path("create/", views.fir_create, name="fir_create"),
    path("<uuid:pk>/update/", views.fir_update, name="fir_update"),
    path("<uuid:pk>/delete/", views.fir_delete, name="fir_delete"),
]