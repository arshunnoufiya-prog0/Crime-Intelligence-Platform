from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("refresh/", views.refresh_view, name="refresh"),
    path("me/", views.MeView.as_view(), name="me"),
    path("change-password/", views.change_password_view, name="change_password"),
    path("users/", views.UserListCreateView.as_view(), name="user_list_create"),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user_detail"),
]