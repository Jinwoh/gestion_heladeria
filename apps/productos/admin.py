from django.contrib import admin
from .models import Categoria, Producto, UnidadMedida


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa", "orden")
    list_filter = ("activa",)
    search_fields = ("nombre",)
    ordering = ("orden", "nombre")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "categoria", "unidad_medida", "precio", "stock_minimo", "activo")
    list_filter = ("tipo", "activo", "categoria", "unidad_medida")
    search_fields = ("nombre", "codigo")
    list_select_related = ("categoria", "unidad_medida")
    ordering = ("nombre",)
    def has_delete_permission(self, request, obj=None): return False


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "abreviatura", "permite_decimales", "activa")
    list_filter = ("activa", "permite_decimales")
    search_fields = ("nombre", "abreviatura")
    def has_delete_permission(self, request, obj=None): return False
