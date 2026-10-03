from django.urls import path
from . import views

app_name = "ventas"

urlpatterns = [
    path("", views.pos_view, name="pos"),
    path("carrito/", views.pos_cart_api, name="cart_api"),
    path("productos/", views.lista_productos, name="productos"),
    path("ticket/<int:venta_id>/", views.ticket_venta, name="ticket"),
    path("<int:venta_id>/anular/", views.anular_venta_view, name="anular"),
]
