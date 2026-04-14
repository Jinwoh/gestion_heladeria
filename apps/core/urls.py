from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from .views import *

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
    path("", home_view, name="home"),
]