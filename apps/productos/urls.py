from django.urls import path

from . import views

app_name = "productos"

urlpatterns = [
    path("", views.productos_view, name="lista"),
    path("nuevo/", views.producto_crear, name="crear"),
    path("<int:pk>/editar/", views.producto_editar, name="editar"),
    path("<int:pk>/estado/", views.producto_toggle, name="toggle"),
]
