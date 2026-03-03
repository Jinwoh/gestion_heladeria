from django.contrib import admin
from .models import Categoria, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa", "orden")
    list_filter = ("activa",)
    search_fields = ("nombre",)
    ordering = ("orden", "nombre")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio", "activo", "codigo", "actualizado_en")
    list_filter = ("activo", "categoria")
    search_fields = ("nombre", "codigo")
    list_select_related = ("categoria",)
    ordering = ("nombre",)