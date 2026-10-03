from django.contrib import admin

from .models import (
    DetalleOrdenCompra,
    DetalleRecepcionCompra,
    MovimientoStock,
    OrdenCompra,
    Proveedor,
    RecepcionCompra,
    SecuenciaOrdenCompra,
    Stock,
)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "ruc", "telefono", "activo", "actualizado_en")
    list_filter = ("activo",)
    search_fields = ("razon_social", "ruc", "persona_contacto")
    def has_delete_permission(self, request, obj=None): return False


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("producto", "cantidad", "actualizado_en")
    search_fields = ("producto__nombre",)
    list_select_related = ("producto",)
    readonly_fields = ("producto", "cantidad", "actualizado_en")
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "producto", "tipo", "cantidad", "stock_anterior", "stock_resultante", "usuario")
    list_filter = ("tipo", "tipo_articulo", "creado_en")
    search_fields = ("producto__nombre", "motivo", "usuario__username")
    list_select_related = ("producto", "usuario")
    readonly_fields = tuple(field.name for field in MovimientoStock._meta.fields)
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


class DetalleOrdenInline(admin.TabularInline):
    model = DetalleOrdenCompra
    extra = 0


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ("numero_formateado", "fecha", "proveedor", "tipo", "estado")
    list_filter = ("estado", "tipo", "fecha")
    search_fields = ("numero", "proveedor__razon_social", "proveedor__ruc")
    inlines = [DetalleOrdenInline]
    def has_delete_permission(self, request, obj=None): return bool(obj and obj.estado == OrdenCompra.Estado.BORRADOR)


class DetalleRecepcionInline(admin.TabularInline):
    model = DetalleRecepcionCompra
    extra = 0
    readonly_fields = ("detalle_orden", "cantidad_recibida", "movimiento_stock")
    def has_add_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(RecepcionCompra)
class RecepcionCompraAdmin(admin.ModelAdmin):
    list_display = ("numero_formateado", "orden_compra", "fecha_recepcion", "usuario_receptor")
    readonly_fields = tuple(field.name for field in RecepcionCompra._meta.fields)
    inlines = [DetalleRecepcionInline]
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(SecuenciaOrdenCompra)
class SecuenciaOrdenCompraAdmin(admin.ModelAdmin):
    readonly_fields = ("nombre", "ultimo_numero")
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
