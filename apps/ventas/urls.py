from django.urls import path
from . import views

app_name = "ventas"

urlpatterns = [
    path("", views.pos_view, name="pos"),  # /pos/
    # luego podés agregar:
    # path("crear/", views.crear_venta, name="crear_venta"),
]