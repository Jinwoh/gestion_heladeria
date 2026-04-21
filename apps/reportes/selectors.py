from decimal import Decimal
from django.db.models import Sum, Count, F
from django.utils import timezone

from apps.ventas.models import Venta, VentaDetalle


def ventas_qs(*, fecha_desde=None, fecha_hasta=None, usuario=None, metodo_pago=None):
    """
    Query base de ventas confirmadas.
    """
    qs = (
        Venta.objects.filter(estado=Venta.Estado.CONFIRMADA)
        .select_related("usuario", "caja_sesion")
    )

    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)

    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    if usuario is not None:
        qs = qs.filter(usuario=usuario)

    if metodo_pago:
        qs = qs.filter(metodo_pago=metodo_pago)

    return qs


def ventas_del_dia_qs(*, fecha=None, usuario=None):
    if fecha is None:
        fecha = timezone.localdate()

    return ventas_qs(
        fecha_desde=fecha,
        fecha_hasta=fecha,
        usuario=usuario,
    )


def resumen_ventas(*, fecha_desde=None, fecha_hasta=None, usuario=None, metodo_pago=None) -> dict:
    qs = ventas_qs(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario,
        metodo_pago=metodo_pago,
    )

    agg = qs.aggregate(
        total_facturado=Sum("total"),
        cantidad_ventas=Count("id"),
    )

    total = agg["total_facturado"] or Decimal("0")
    cantidad = agg["cantidad_ventas"] or 0
    ticket_promedio = (total / cantidad) if cantidad > 0 else Decimal("0")

    return {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "cantidad_ventas": cantidad,
        "total_facturado": total,
        "ticket_promedio": ticket_promedio,
    }


def resumen_ventas_del_dia(*, fecha=None, usuario=None) -> dict:
    if fecha is None:
        fecha = timezone.localdate()

    data = resumen_ventas(
        fecha_desde=fecha,
        fecha_hasta=fecha,
        usuario=usuario,
    )
    data["fecha"] = fecha
    return data


def ventas_por_metodo_pago(*, fecha_desde=None, fecha_hasta=None, usuario=None):
    qs = ventas_qs(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario,
    )

    return qs.values("metodo_pago").annotate(
        cantidad=Count("id"),
        total=Sum("total"),
    ).order_by("-total")


def ventas_por_usuario(*, fecha_desde=None, fecha_hasta=None, usuario=None):
    qs = ventas_qs(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario,
    )

    return qs.values(
        "usuario__id",
        "usuario__username",
    ).annotate(
        cantidad=Count("id"),
        total=Sum("total"),
    ).order_by("-total")


def ventas_por_caja(*, fecha_desde=None, fecha_hasta=None, usuario=None):
    qs = ventas_qs(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario,
    )

    return qs.values(
        "caja_sesion__id",
    ).annotate(
        cantidad=Count("id"),
        total=Sum("total"),
    ).order_by("-total")


def top_productos_vendidos(*, fecha_desde=None, fecha_hasta=None, usuario=None, limit=10):
    detalles = VentaDetalle.objects.filter(
        venta__estado=Venta.Estado.CONFIRMADA
    ).select_related("producto", "venta")

    if fecha_desde:
        detalles = detalles.filter(venta__fecha__date__gte=fecha_desde)

    if fecha_hasta:
        detalles = detalles.filter(venta__fecha__date__lte=fecha_hasta)

    if usuario is not None:
        detalles = detalles.filter(venta__usuario=usuario)

    return detalles.values(
        "producto__id",
        "producto__nombre",
    ).annotate(
        cantidad_total=Sum("cantidad"),
        total_vendido=Sum("subtotal"),
    ).order_by("-cantidad_total", "-total_vendido")[:limit]


def ventas_por_producto(*, fecha_desde=None, fecha_hasta=None, usuario=None):
    detalles = VentaDetalle.objects.filter(
        venta__estado=Venta.Estado.CONFIRMADA
    ).select_related("producto", "venta")

    if fecha_desde:
        detalles = detalles.filter(venta__fecha__date__gte=fecha_desde)

    if fecha_hasta:
        detalles = detalles.filter(venta__fecha__date__lte=fecha_hasta)

    if usuario is not None:
        detalles = detalles.filter(venta__usuario=usuario)

    return detalles.values(
        "producto__id",
        "producto__nombre",
    ).annotate(
        cantidad_total=Sum("cantidad"),
        total_vendido=Sum("subtotal"),
    ).order_by("-total_vendido", "producto__nombre")