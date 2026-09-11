from django.contrib.auth.views import LoginView
from django.urls import path
from .views import actualizar_meta_dashboard, home_view, logout_view

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(
            template_name="core/login.html",
            redirect_authenticated_user=True
        ),
        name="login"
    ),
    path("logout/", logout_view, name="logout"),
    path("dashboard/meta/", actualizar_meta_dashboard, name="actualizar_meta_dashboard"),
    path("", home_view, name="home"),
]
