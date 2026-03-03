from django.urls import path
from . import views

app_name = "reportes"

urlpatterns = [
    path("dia/", views.reporte_dia, name="reporte_dia"),
]