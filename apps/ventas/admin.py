from django.contrib import admin

from .models import Venta, VentaPago, VentaDetalle


class VentaPagoInline(admin.TabularInline):
    model = VentaPago
    extra = 0
    fields = ("metodo_pago", "monto")
    readonly_fields = ("metodo_pago", "monto")
    can_delete = False


class VentaDetalleInline(admin.TabularInline):
    model = VentaDetalle
    extra = 0
    fields = ("producto", "cantidad", "precio_unitario", "subtotal")
    readonly_fields = ("producto", "cantidad", "precio_unitario", "subtotal")
    can_delete = False


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fecha",
        "usuario",
        "caja_sesion",
        "total",
        "vuelto",
        "estado",
        "resumen_pagos",
    )
    list_filter = (
        "estado",
        "fecha",
        "usuario",
        "caja_sesion",
    )
    search_fields = (
        "id",
        "usuario__username",
        "caja_sesion__id",
    )
    readonly_fields = (
        "fecha",
        "usuario",
        "caja_sesion",
        "total",
        "vuelto",
        "estado",
    )
    inlines = [VentaPagoInline, VentaDetalleInline]
    ordering = ("-fecha",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Pagos")
    def resumen_pagos(self, obj):
        pagos = obj.pagos.all()
        if not pagos:
            return "-"
        return " | ".join(
            f"{p.get_metodo_pago_display()}: {p.monto}" for p in pagos
        )


@admin.register(VentaPago)
class VentaPagoAdmin(admin.ModelAdmin):
    list_display = ("id", "venta", "metodo_pago", "monto")
    list_filter = ("metodo_pago",)
    search_fields = ("venta__id",)
    readonly_fields = ("venta", "metodo_pago", "monto")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VentaDetalle)
class VentaDetalleAdmin(admin.ModelAdmin):
    list_display = ("id", "venta", "producto", "cantidad", "precio_unitario", "subtotal")
    list_filter = ("producto",)
    search_fields = ("venta__id", "producto__nombre")
    readonly_fields = ("venta", "producto", "cantidad", "precio_unitario", "subtotal")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False