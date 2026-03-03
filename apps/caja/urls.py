from django.urls import path
from . import views

app_name = "caja"

urlpatterns = [
    path("apertura/", views.apertura_caja, name="apertura"),
    path("arqueo/", views.arqueo_caja, name="arqueo"),
    path("cierre/", views.cierre_caja, name="cierre"),
]