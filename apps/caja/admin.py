from django.contrib import admin

from .models import Caja, CajaSesion, MovimientoCaja


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ("numero", "nombre", "activa", "usuarios_habilitados_lista")
    list_filter = ("activa",)
    search_fields = ("numero", "nombre", "usuarios_habilitados__username")
    filter_horizontal = ("usuarios_habilitados",)

    @admin.display(description="Usuarios habilitados")
    def usuarios_habilitados_lista(self, obj):
        usuarios = obj.usuarios_habilitados.all()
        if not usuarios:
            return "-"
        return ", ".join(u.username for u in usuarios)


class MovimientoCajaInline(admin.TabularInline):
    model = MovimientoCaja
    extra = 0
    readonly_fields = (
        "tipo",
        "monto",
        "metodo_pago",
        "referencia",
        "motivo",
        "usuario",
        "creado_en",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CajaSesion)
class CajaSesionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "caja",
        "usuario",
        "estado",
        "fecha_apertura",
        "fecha_cierre",
        "monto_apertura",
        "monto_cierre_declarado",
    )
    list_filter = ("estado", "caja", "usuario", "fecha_apertura", "fecha_cierre")
    search_fields = ("id", "caja__numero", "usuario__username", "notas", "observacion_diferencia")
    readonly_fields = (
        "caja",
        "usuario",
        "estado",
        "fecha_apertura",
        "fecha_cierre",
        "monto_apertura",
        "monto_cierre_declarado",
        "notas",
        "observacion_diferencia",
    )
    inlines = [MovimientoCajaInline]
    ordering = ("-fecha_apertura",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "caja_sesion",
        "tipo",
        "metodo_pago",
        "monto",
        "usuario",
        "creado_en",
        "referencia",
    )
    list_filter = ("tipo", "metodo_pago", "usuario", "creado_en")
    search_fields = ("id", "caja_sesion__caja__numero", "usuario__username", "referencia", "motivo")
    readonly_fields = (
        "caja_sesion",
        "tipo",
        "metodo_pago",
        "monto",
        "referencia",
        "motivo",
        "usuario",
        "creado_en",
    )
    ordering = ("-creado_en",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False