from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.ventas.models import Venta
from .selectors import ventas_del_dia_qs, resumen_ventas_del_dia


@login_required
def reporte_dia(request):
    fecha = timezone.localdate()

    # Permiso: si tiene ventas.view_venta ve global, si no ve solo lo suyo
    puede_ver_global = request.user.has_perm("ventas.view_venta")

    usuario_filtro = None if puede_ver_global else request.user

    kpis = resumen_ventas_del_dia(fecha=fecha, usuario=usuario_filtro)

    ventas = (
        ventas_del_dia_qs(fecha=fecha, usuario=usuario_filtro)
        .order_by("-fecha")[:50]
        .prefetch_related("detalles", "detalles__producto")
    )

    ctx = {
        "kpis": kpis,
        "ventas": ventas,
        "puede_ver_global": puede_ver_global,
    }
    return render(request, "reportes/dia.html", ctx)