from django.urls import path
from . import views

app_name = "caja"

urlpatterns = [
    path("apertura/", views.apertura_caja, name="apertura"),
    path("arqueo/", views.arqueo_caja, name="arqueo"),
    path("movimiento/", views.movimiento_caja, name="movimiento"),
    path("cierre/", views.cierre_caja, name="cierre"),
    path("historial-cierres/", views.historial_cierres, name="historial_cierres"),
]