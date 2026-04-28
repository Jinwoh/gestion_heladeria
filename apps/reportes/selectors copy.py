from decimal import Decimal
from datetime import timedelta

from django.db.models import Sum, Count, Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.ventas.models import Venta, VentaDetalle
from apps.productos.models import Producto
from apps.caja.models import CajaSesion, MovimientoCaja


def ventas_qs(*, fecha_desde=None, fecha_hasta=None, usuario=None, metodo_pago=None):
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
        total_facturado=Coalesce(Sum("total"), Decimal("0")),
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
        total=Coalesce(Sum("total"), Decimal("0")),
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
        total=Coalesce(Sum("total"), Decimal("0")),
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
        total=Coalesce(Sum("total"), Decimal("0")),
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
        cantidad_total=Coalesce(Sum("cantidad"), 0),
        total_vendido=Coalesce(Sum("subtotal"), Decimal("0")),
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
        cantidad_total=Coalesce(Sum("cantidad"), 0),
        total_vendido=Coalesce(Sum("subtotal"), Decimal("0")),
    ).order_by("-total_vendido", "producto__nombre")


def productos_sin_ventas(*, fecha_desde=None, fecha_hasta=None, usuario=None, solo_activos=True, limit=20):
    ventas_subquery = VentaDetalle.objects.filter(
        producto_id=OuterRef("pk"),
        venta__estado=Venta.Estado.CONFIRMADA,
    )

    if fecha_desde:
        ventas_subquery = ventas_subquery.filter(venta__fecha__date__gte=fecha_desde)

    if fecha_hasta:
        ventas_subquery = ventas_subquery.filter(venta__fecha__date__lte=fecha_hasta)

    if usuario is not None:
        ventas_subquery = ventas_subquery.filter(venta__usuario=usuario)

    productos = Producto.objects.all()

    if solo_activos:
        productos = productos.filter(activo=True)

    return (
        productos
        .annotate(tuvo_ventas=Exists(ventas_subquery))
        .filter(tuvo_ventas=False)
        .select_related("categoria")
        .order_by("categoria__nombre", "nombre")[:limit]
    )


def productos_baja_rotacion(*, fecha_desde=None, fecha_hasta=None, usuario=None, limit=20):
    detalles = VentaDetalle.objects.filter(
        venta__estado=Venta.Estado.CONFIRMADA
    )

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
        cantidad_total=Coalesce(Sum("cantidad"), 0),
        total_vendido=Coalesce(Sum("subtotal"), Decimal("0")),
    ).order_by("cantidad_total", "producto__nombre")[:limit]


def ventas_por_dia(*, fecha_desde=None, fecha_hasta=None, usuario=None, metodo_pago=None):
    qs = ventas_qs(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario,
        metodo_pago=metodo_pago,
    )

    return qs.values("fecha__date").annotate(
        cantidad=Count("id"),
        total=Coalesce(Sum("total"), Decimal("0")),
    ).order_by("fecha__date")


def comparativa_periodo(*, fecha_desde, fecha_hasta, usuario=None, metodo_pago=None):
    dias = (fecha_hasta - fecha_desde).days + 1
    previo_hasta = fecha_desde - timedelta(days=1)
    previo_desde = previo_hasta - timedelta(days=dias - 1)

    actual = resumen_ventas(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario=usuario,
        metodo_pago=metodo_pago,
    )

    previo = resumen_ventas(
        fecha_desde=previo_desde,
        fecha_hasta=previo_hasta,
        usuario=usuario,
        metodo_pago=metodo_pago,
    )

    total_actual = actual["total_facturado"]
    total_previo = previo["total_facturado"]

    if total_previo > 0:
        variacion = ((total_actual - total_previo) / total_previo) * 100
    else:
        variacion = Decimal("0")

    return {
        "actual": actual,
        "previo": previo,
        "previo_desde": previo_desde,
        "previo_hasta": previo_hasta,
        "variacion_porcentual": variacion,
    }


def cierres_caja_qs(*, fecha_desde=None, fecha_hasta=None, usuario=None):
    qs = CajaSesion.objects.select_related("usuario")

    if fecha_desde:
        qs = qs.filter(fecha_apertura__date__gte=fecha_desde)

    if fecha_hasta:
        qs = qs.filter(fecha_apertura__date__lte=fecha_hasta)

    if usuario is not None:
        qs = qs.filter(usuario=usuario)

    return qs.annotate(
        total_ventas=Coalesce(
            Sum("ventas__total", filter=Q(ventas__estado=Venta.Estado.CONFIRMADA)),
            Decimal("0"),
        ),
        total_ingresos=Coalesce(
            Sum("movimientos__monto", filter=Q(movimientos__tipo=MovimientoCaja.Tipo.INGRESO)),
            Decimal("0"),
        ),
        total_egresos=Coalesce(
            Sum("movimientos__monto", filter=Q(movimientos__tipo=MovimientoCaja.Tipo.EGRESO)),
            Decimal("0"),
        ),
    ).order_by("-fecha_apertura")