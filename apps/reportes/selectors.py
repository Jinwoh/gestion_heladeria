from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone

from apps.ventas.models import Venta


def ventas_del_dia_qs(*, fecha=None, usuario=None):
    """
    Devuelve queryset de ventas CONFIRMADAS del día.
    - fecha: date (por defecto hoy en timezone local)
    - usuario: filtra por cajero si se pasa
    """
    if fecha is None:
        fecha = timezone.localdate()

    qs = Venta.objects.filter(
        estado=Venta.Estado.CONFIRMADA,
        fecha__date=fecha,
    ).select_related("usuario", "caja_sesion")

    if usuario is not None:
        qs = qs.filter(usuario=usuario)

    return qs


def resumen_ventas_del_dia(*, fecha=None, usuario=None) -> dict:
    """
    KPIs:
    - cantidad_ventas
    - total_facturado
    - ticket_promedio
    """
    qs = ventas_del_dia_qs(fecha=fecha, usuario=usuario)

    agg = qs.aggregate(
        total_facturado=Sum("total"),
        cantidad_ventas=Count("id"),
    )

    total = agg["total_facturado"] or Decimal("0")
    cantidad = agg["cantidad_ventas"] or 0

    ticket_promedio = (total / cantidad) if cantidad > 0 else Decimal("0")

    return {
        "fecha": fecha or timezone.localdate(),
        "cantidad_ventas": cantidad,
        "total_facturado": total,
        "ticket_promedio": ticket_promedio,
    }