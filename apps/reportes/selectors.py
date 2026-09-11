from decimal import Decimal
from datetime import datetime, time, timedelta

from django.db.models import DecimalField, Sum, Count, Exists, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.ventas.models import Venta, VentaDetalle, VentaPago
from apps.productos.models import Producto
from apps.caja.models import CajaSesion, MovimientoCaja


def _inicio_dia(fecha):
    valor = datetime.combine(fecha, time.min)
    return timezone.make_aware(valor, timezone.get_current_timezone())


def ventas_qs(*, fecha_desde=None, fecha_hasta=None, usuario=None, metodo_pago=None):
    qs = (
        Venta.objects.filter(estado=Venta.Estado.CONFIRMADA)
        .select_related("usuario", "caja_sesion")
        .prefetch_related("pagos")
    )

    if fecha_desde:
        qs = qs.filter(fecha__gte=_inicio_dia(fecha_desde))

    if fecha_hasta:
        qs = qs.filter(fecha__lt=_inicio_dia(fecha_hasta + timedelta(days=1)))

    if usuario is not None:
        qs = qs.filter(usuario=usuario)

    if metodo_pago:
        qs = qs.filter(pagos__metodo_pago=metodo_pago).distinct()

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
        cantidad_ventas=Count("id", distinct=True),
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
    pagos = VentaPago.objects.filter(
        venta__estado=Venta.Estado.CONFIRMADA
    )

    if fecha_desde:
        pagos = pagos.filter(venta__fecha__gte=_inicio_dia(fecha_desde))

    if fecha_hasta:
        pagos = pagos.filter(venta__fecha__lt=_inicio_dia(fecha_hasta + timedelta(days=1)))

    if usuario is not None:
        pagos = pagos.filter(venta__usuario=usuario)

    return pagos.values("metodo_pago").annotate(
        cantidad=Count("venta", distinct=True),
        total=Coalesce(Sum("monto"), Decimal("0")),
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
        cantidad=Count("id", distinct=True),
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
        cantidad=Count("id", distinct=True),
        total=Coalesce(Sum("total"), Decimal("0")),
    ).order_by("-total")


def top_productos_vendidos(*, fecha_desde=None, fecha_hasta=None, usuario=None, limit=10):
    detalles = VentaDetalle.objects.filter(
        venta__estado=Venta.Estado.CONFIRMADA
    ).select_related("producto", "venta")

    if fecha_desde:
        detalles = detalles.filter(venta__fecha__gte=_inicio_dia(fecha_desde))

    if fecha_hasta:
        detalles = detalles.filter(venta__fecha__lt=_inicio_dia(fecha_hasta + timedelta(days=1)))

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
        detalles = detalles.filter(venta__fecha__gte=_inicio_dia(fecha_desde))

    if fecha_hasta:
        detalles = detalles.filter(venta__fecha__lt=_inicio_dia(fecha_hasta + timedelta(days=1)))

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
        ventas_subquery = ventas_subquery.filter(venta__fecha__gte=_inicio_dia(fecha_desde))

    if fecha_hasta:
        ventas_subquery = ventas_subquery.filter(venta__fecha__lt=_inicio_dia(fecha_hasta + timedelta(days=1)))

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
        detalles = detalles.filter(venta__fecha__gte=_inicio_dia(fecha_desde))

    if fecha_hasta:
        detalles = detalles.filter(venta__fecha__lt=_inicio_dia(fecha_hasta + timedelta(days=1)))

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
        cantidad=Count("id", distinct=True),
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
    qs = CajaSesion.objects.select_related("usuario", "caja").filter(
        estado=CajaSesion.Estado.CERRADA
    )

    if fecha_desde:
        qs = qs.filter(fecha_apertura__gte=_inicio_dia(fecha_desde))

    if fecha_hasta:
        qs = qs.filter(fecha_apertura__lt=_inicio_dia(fecha_hasta + timedelta(days=1)))

    if usuario is not None:
        qs = qs.filter(usuario=usuario)

    importe = DecimalField(max_digits=12, decimal_places=2)
    ventas = (
        Venta.objects.filter(caja_sesion_id=OuterRef("pk"), estado=Venta.Estado.CONFIRMADA)
        .values("caja_sesion_id")
        .annotate(total=Sum("total"))
        .values("total")
    )
    ingresos = (
        MovimientoCaja.objects.filter(
            caja_sesion_id=OuterRef("pk"),
            tipo__in=[MovimientoCaja.Tipo.INGRESO, MovimientoCaja.Tipo.AJUSTE_INGRESO],
        )
        .values("caja_sesion_id")
        .annotate(total=Sum("monto"))
        .values("total")
    )
    egresos = (
        MovimientoCaja.objects.filter(
            caja_sesion_id=OuterRef("pk"),
            tipo__in=[MovimientoCaja.Tipo.EGRESO, MovimientoCaja.Tipo.AJUSTE_EGRESO],
        )
        .values("caja_sesion_id")
        .annotate(total=Sum("monto"))
        .values("total")
    )

    return qs.annotate(
        total_ventas=Coalesce(
            Subquery(ventas, output_field=importe),
            Decimal("0"),
        ),
        total_ingresos=Coalesce(
            Subquery(ingresos, output_field=importe),
            Decimal("0"),
        ),
        total_egresos=Coalesce(
            Subquery(egresos, output_field=importe),
            Decimal("0"),
        ),
    ).order_by("-fecha_apertura")
