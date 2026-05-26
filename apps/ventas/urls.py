from django.urls import path
from . import views

app_name = "ventas"

urlpatterns = [
    path("", views.pos_view, name="pos"),
    path("productos/", views.lista_productos, name="productos"),
    path("ticket/<int:venta_id>/", views.ticket_venta, name="ticket"),
]