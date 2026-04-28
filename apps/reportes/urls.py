from django.urls import path
from . import views

app_name = "reportes"

urlpatterns = [
    path("dia/", views.reporte_dia, name="reporte_dia"),
    path("general/", views.reporte_general, name="reporte_general"),
    path("venta/<int:venta_id>/", views.detalle_venta, name="detalle_venta"),
]