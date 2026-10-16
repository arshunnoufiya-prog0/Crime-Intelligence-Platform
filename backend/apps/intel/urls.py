from django.urls import path

from . import views

urlpatterns = [
    path("query/", views.QueryView.as_view(), name="intel_query"),
    path("graph/subgraph/<str:fir_id>/", views.SubgraphView.as_view(), name="intel_subgraph"),
    path("graph/network/<str:person_name>/", views.NetworkView.as_view(), name="intel_network"),
    path("profile/person/<str:person_name>/", views.ProfileView.as_view(), name="intel_profile"),
]
