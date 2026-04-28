from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime

from apps.ventas.models import Venta
from .selectors import (
    ventas_del_dia_qs,
    resumen_ventas_del_dia,
    resumen_ventas,
    ventas_qs,
    ventas_por_metodo_pago,
    ventas_por_usuario,
    ventas_por_caja,
    ventas_por_producto,
    top_productos_vendidos,
)

User = get_user_model()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@login_required
def reporte_dia(request):
    fecha = timezone.localdate()

    puede_ver_global = request.user.has_perm("ventas.view_venta")
    usuario_filtro = None if puede_ver_global else request.user

    kpis = resumen_ventas_del_dia(fecha=fecha, usuario=usuario_filtro)

    ventas = (
        ventas_del_dia_qs(fecha=fecha, usuario=usuario_filtro)
        .order_by("-fecha")[:50]
        .prefetch_related("detalles", "detalles__producto")
    )

    por_metodo = ventas_por_metodo_pago(
        fecha_desde=fecha,
        fecha_hasta=fecha,
        usuario=usuario_filtro,
    )

    top_productos = top_productos_vendidos(
        fecha_desde=fecha,
        fecha_hasta=fecha,
        usuario=usuario_filtro,
        limit=5,
    )

    ctx = {
        "kpis": kpis,
        "ventas": ventas,
        "por_metodo": por_metodo,
        "top_productos": top_productos,
        "puede_ver_global": puede_ver_global,
    }
    return render(request, "reportes/dia.html", ctx)


@login_required
def reporte_general(request):
    hoy = timezone.localdate()

    fecha_desde = _parse_date(request.GET.get("fecha_desde")) or hoy
    fecha_hasta = _parse_date(request.GET.get("fecha_hasta")) or hoy
    metodo_pago = request.GET.get("metodo_pago", "").strip()
    usuario_id = request.GET.get("usuario", "").strip()

    puede_ver_global = request.user.has_perm("ventas.view_venta")

    usuario_filtro = None
    usuarios = User.objects.filter(is_active=True).order_by("username")

    if puede_ver_global:
        if usuario_id:
            try:
                usuario_filtro = User.objects.get(pk=int(usuario_id))
            except (ValueError, User.DoesNotExist):
                usuario_filtro = None
    else:
        usuario_filtro = request.user

    kpis = resumen_ventas(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario_filtro,
        metodo_pago=metodo_pago or None,
    )

    ventas = (
        ventas_qs(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            usuario=usuario_filtro,
            metodo_pago=metodo_pago or None,
        )
        .order_by("-fecha")
        .prefetch_related("detalles", "detalles__producto")[:100]
    )

    por_metodo = ventas_por_metodo_pago(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario_filtro,
    )

    por_usuario = ventas_por_usuario(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=None if puede_ver_global else request.user,
    )

    por_caja = ventas_por_caja(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario_filtro,
    )

    por_producto = ventas_por_producto(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario_filtro,
    )[:20]

    top_productos = top_productos_vendidos(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario_filtro,
        limit=10,
    )

    ctx = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "metodo_pago": metodo_pago,
        "usuario_id": usuario_id,
        "usuarios": usuarios,
        "kpis": kpis,
        "ventas": ventas,
        "por_metodo": por_metodo,
        "por_usuario": por_usuario,
        "por_caja": por_caja,
        "por_producto": por_producto,
        "top_productos": top_productos,
        "puede_ver_global": puede_ver_global,
    }
    return render(request, "reportes/general.html", ctx)