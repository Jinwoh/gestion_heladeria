from django.urls import path
from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.stock_list, name="stock"),
    path("movimiento/", views.stock_movement, name="movimiento"),
    path("movimientos/", views.movimientos_list, name="movimientos"),
    path("proveedores/", views.proveedores_list, name="proveedores"),
    path("proveedores/nuevo/", views.proveedor_crear, name="proveedor_crear"),
    path("proveedores/<int:pk>/editar/", views.proveedor_editar, name="proveedor_editar"),
    path("proveedores/<int:pk>/estado/", views.proveedor_toggle, name="proveedor_toggle"),
    path("compras/ordenes/", views.ordenes_list, name="ordenes"),
    path("compras/ordenes/nueva/", views.orden_crear, name="orden_crear"),
    path("compras/ordenes/<int:pk>/", views.orden_detalle, name="orden_detalle"),
    path("compras/ordenes/<int:pk>/editar/", views.orden_editar, name="orden_editar"),
    path("compras/ordenes/<int:pk>/emitir/", views.orden_emitir, name="orden_emitir"),
    path("compras/ordenes/<int:pk>/cancelar/", views.orden_cancelar, name="orden_cancelar"),
    path("compras/ordenes/<int:pk>/recibir/", views.orden_recibir, name="orden_recibir"),
    path("compras/recepciones/", views.recepciones_list, name="recepciones"),
    path("compras/recepciones/<int:pk>/", views.recepcion_detalle, name="recepcion_detalle"),
]
