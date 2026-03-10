from django.contrib import admin
from .models import Venta, VentaDetalle


class VentaDetalleInline(admin.TabularInline):
    model = VentaDetalle
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "usuario", "total", "estado", "caja_sesion")
    list_filter = ("estado", "fecha")
    search_fields = ("id", "usuario__username")
    inlines = [VentaDetalleInline]
    date_hierarchy = "fecha"


@admin.register(VentaDetalle)
class VentaDetalleAdmin(admin.ModelAdmin):
    list_display = ("venta", "producto", "cantidad", "precio_unitario", "subtotal")
    search_fields = ("venta__id", "producto__nombre")