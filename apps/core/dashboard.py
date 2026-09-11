from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.ventas.models import Venta, VentaDetalle, VentaPago
from .models import ConfiguracionDashboard


MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
MESES_CORTOS = tuple(mes[:3].capitalize() for mes in MESES)
DINERO = DecimalField(max_digits=14, decimal_places=2)


def _inicio_mes(fecha, desplazamiento=0):
    indice = fecha.year * 12 + fecha.month - 1 + desplazamiento
    return fecha.replace(year=indice // 12, month=indice % 12 + 1, day=1)


def _inicio_dia(fecha):
    return timezone.make_aware(
        datetime.combine(fecha, time.min), timezone.get_current_timezone()
    )


def _rango(periodo):
    hoy = timezone.localdate()
    if periodo == "12m":
        inicio = _inicio_mes(hoy, -11)
    elif periodo == "ytd":
        inicio = hoy.replace(month=1, day=1)
    else:
        periodo = "6m"
        inicio = _inicio_mes(hoy, -5)

    fin_exclusivo = hoy + timedelta(days=1)
    dias = fin_exclusivo - inicio
    previo_fin = inicio
    previo_inicio = inicio - dias
    return periodo, inicio, fin_exclusivo, previo_inicio, previo_fin


def _delta(actual, anterior):
    actual = Decimal(actual or 0)
    anterior = Decimal(anterior or 0)
    if anterior == 0:
        return 100.0 if actual > 0 else 0.0
    return float(((actual - anterior) / anterior * 100).quantize(Decimal("0.1")))


def _ventas_rango(usuario, inicio, fin, globales):
    qs = Venta.objects.filter(
        estado=Venta.Estado.CONFIRMADA,
        fecha__gte=_inicio_dia(inicio),
        fecha__lt=_inicio_dia(fin),
    )
    if not globales:
        qs = qs.filter(usuario=usuario)
    return qs


def _resumen(qs):
    datos = qs.aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DINERO),
        operaciones=Count("pk"),
    )
    datos["ticket_promedio"] = (
        datos["total"] / datos["operaciones"] if datos["operaciones"] else Decimal("0")
    )
    return datos


def _clientes_nuevos(usuario, inicio, fin, globales):
    qs = Cliente.objects.filter(
        creado_en__gte=_inicio_dia(inicio),
        creado_en__lt=_inicio_dia(fin),
    )
    if not globales:
        qs = qs.filter(
            ventas__usuario=usuario,
            ventas__estado=Venta.Estado.CONFIRMADA,
            ventas__fecha__gte=_inicio_dia(inicio),
            ventas__fecha__lt=_inicio_dia(fin),
        ).distinct()
    return qs.count()


def _etiqueta_rango(inicio, fin_exclusivo):
    fin = fin_exclusivo - timedelta(days=1)
    if inicio.year == fin.year:
        return f"{MESES[inicio.month - 1].capitalize()} — {MESES[fin.month - 1]} {fin.year}"
    return (
        f"{MESES[inicio.month - 1].capitalize()} {inicio.year} — "
        f"{MESES[fin.month - 1]} {fin.year}"
    )


def construir_dashboard(*, usuario, periodo):
    periodo, inicio, fin, previo_inicio, previo_fin = _rango(periodo)
    globales = usuario.is_superuser or usuario.has_perm("ventas.view_global_reports")
    ventas = _ventas_rango(usuario, inicio, fin, globales)
    ventas_previas = _ventas_rango(usuario, previo_inicio, previo_fin, globales)
    actual = _resumen(ventas)
    anterior = _resumen(ventas_previas)

    clientes = _clientes_nuevos(usuario, inicio, fin, globales)
    clientes_previos = _clientes_nuevos(usuario, previo_inicio, previo_fin, globales)
    kpis = [
        {
            "label": "Ventas totales",
            "value": actual["total"],
            "format": "currency",
            "delta": _delta(actual["total"], anterior["total"]),
        },
        {
            "label": "Operaciones",
            "value": actual["operaciones"],
            "format": "number",
            "delta": _delta(actual["operaciones"], anterior["operaciones"]),
        },
        {
            "label": "Ticket promedio",
            "value": actual["ticket_promedio"],
            "format": "currency",
            "delta": _delta(actual["ticket_promedio"], anterior["ticket_promedio"]),
        },
        {
            "label": "Nuevos clientes",
            "value": clientes,
            "format": "number",
            "delta": _delta(clientes, clientes_previos),
        },
    ]
    for kpi in kpis:
        kpi["direction"] = "up" if kpi["delta"] >= 0 else "down"
        kpi["delta_abs"] = abs(kpi["delta"])

    pagos_qs = VentaPago.objects.filter(venta__in=ventas)
    pagos = {
        fila["metodo_pago"]: fila["total"]
        for fila in pagos_qs.values("metodo_pago").annotate(
            total=Coalesce(Sum("monto"), Decimal("0"), output_field=DINERO)
        )
    }
    metodos = [
        (VentaPago.MetodoPago.EFECTIVO, "Efectivo"),
        (VentaPago.MetodoPago.TARJETA, "Tarjeta"),
        (VentaPago.MetodoPago.QR, "QR"),
    ]

    tendencia_db = {
        fila["mes"].date(): fila
        for fila in ventas.annotate(mes=TruncMonth("fecha"))
        .values("mes")
        .annotate(
            total=Coalesce(Sum("total"), Decimal("0"), output_field=DINERO),
            operaciones=Count("pk"),
        )
        .order_by("mes")
    }
    meses = []
    cursor = inicio.replace(day=1)
    ultimo_mes = (fin - timedelta(days=1)).replace(day=1)
    while cursor <= ultimo_mes:
        meses.append(cursor)
        cursor = _inicio_mes(cursor, 1)

    productos = list(
        VentaDetalle.objects.filter(venta__in=ventas)
        .values("producto__nombre")
        .annotate(total=Coalesce(Sum("subtotal"), Decimal("0"), output_field=DINERO))
        .order_by("-total")[:5]
    )
    total_productos = sum((fila["total"] for fila in productos), Decimal("0"))

    operaciones = actual["operaciones"]

    vendedores = list(
        ventas.values("usuario__username")
        .annotate(
            total=Coalesce(Sum("total"), Decimal("0"), output_field=DINERO),
            operaciones=Count("pk"),
        )
        .order_by("-total")
    )
    for vendedor in vendedores:
        vendedor["ticket_promedio"] = (
            vendedor["total"] / vendedor["operaciones"]
            if vendedor["operaciones"]
            else Decimal("0")
        )
        vendedor["participacion"] = (
            round(float(vendedor["total"] / actual["total"] * 100), 1)
            if actual["total"]
            else 0
        )

    configuracion = (
        ConfiguracionDashboard.objects.select_related("actualizada_por")
        .filter(pk=1)
        .first()
    )
    meta_mensual = (
        configuracion.meta_mensual
        if configuracion
        else settings.DASHBOARD_META_MENSUAL
    )
    meta_periodo = meta_mensual * max(len(meses), 1)
    meta_pct = min(round(float(actual["total"] / meta_periodo * 100)), 100) if meta_periodo else 0

    etiquetas_tendencia = [
        f"{MESES_CORTOS[mes.month - 1]} {str(mes.year)[2:]}" for mes in meses
    ]
    ventas_tendencia = [
        float(tendencia_db.get(mes, {}).get("total", 0)) for mes in meses
    ]
    operaciones_tendencia = [
        tendencia_db.get(mes, {}).get("operaciones", 0) for mes in meses
    ]

    charts = {
        "payments": {
            "labels": [etiqueta for _, etiqueta in metodos],
            "data": [float(pagos.get(codigo, 0)) for codigo, _ in metodos],
        },
        "trend": {
            "labels": etiquetas_tendencia,
            "data": ventas_tendencia,
        },
        "timeline": {
            "labels": etiquetas_tendencia,
            "sales": ventas_tendencia,
            "operations": operaciones_tendencia,
        },
        "products": {
            "labels": [fila["producto__nombre"] for fila in productos],
            "data": [
                round(float(fila["total"] / total_productos * 100), 1)
                if total_productos else 0
                for fila in productos
            ],
        },
        "goal": {"current": float(actual["total"]), "target": float(meta_periodo)},
    }

    return {
        "periodo": periodo,
        "rango": _etiqueta_rango(inicio, fin),
        "kpis": kpis,
        "charts": charts,
        "meta_periodo": meta_periodo,
        "meta_mensual": meta_mensual,
        "meta_pct": meta_pct,
        "meta_actualizada_en": configuracion.actualizada_en if configuracion else None,
        "meta_actualizada_por": configuracion.actualizada_por if configuracion else None,
        "operaciones": operaciones,
        "vendedores": vendedores,
        "globales": globales,
    }
