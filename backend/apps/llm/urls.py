from django.urls import path
from . import views

urlpatterns = [
    path("graph/query/", views.GraphQueryView.as_view(), name="graph_query"),
    path("graph/subgraph/<str:fir_id>/", views.SubgraphView.as_view(), name="graph_subgraph"),
    path("graph/history/", views.GraphQueryHistoryView.as_view(), name="graph_history"),
]