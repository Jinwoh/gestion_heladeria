from django.contrib import admin
from .models import Stock, MovimientoStock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("producto", "cantidad", "actualizado_en")
    search_fields = ("producto__nombre",)
    list_select_related = ("producto",)


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "producto", "tipo", "cantidad", "usuario", "motivo")
    list_filter = ("tipo", "creado_en")
    search_fields = ("producto__nombre", "motivo", "usuario__username")
    list_select_related = ("producto", "usuario")
    date_hierarchy = "creado_en"