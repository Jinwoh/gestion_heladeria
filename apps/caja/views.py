from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import redirect, render

from apps.caja.models import CajaSesion, MovimientoCaja

from .forms import AperturaCajaForm, CierreCajaForm, MovimientoCajaForm
from .services import (
    abrir_caja,
    cerrar_caja,
    get_caja_abierta,
    registrar_movimiento,
)


@login_required
def apertura_caja(request):
    caja_abierta = get_caja_abierta(request.user)

    if request.method == "POST":
        form = AperturaCajaForm(request.POST, usuario=request.user)
        if form.is_valid():
            try:
                abrir_caja(
                    usuario=request.user,
                    caja=form.cleaned_data["caja"],
                    monto_apertura=form.cleaned_data["monto_apertura"],
                    notas=form.cleaned_data.get("notas", ""),
                )
                messages.success(request, "Caja abierta correctamente.")
                return redirect("caja:arqueo")
            except ValidationError as e:
                messages.error(request, e.message)
        else:
            messages.error(request, "Formulario inválido. Revisá los campos.")
    else:
        form = AperturaCajaForm(
            initial={"monto_apertura": 0},
            usuario=request.user,
        )

    return render(
        request,
        "caja/apertura.html",
        {
            "form": form,
            "caja": caja_abierta,
        },
    )


@login_required
def arqueo_caja(request):
    caja = get_caja_abierta(request.user)

    if not caja:
        messages.warning(
            request,
            "La caja está cerrada. Debes abrir una caja para continuar."
        )
        return redirect("caja:apertura")

    movs = caja.movimientos.all()

    total_ingresos = movs.filter(
        tipo=MovimientoCaja.Tipo.INGRESO
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    total_egresos = movs.filter(
        tipo=MovimientoCaja.Tipo.EGRESO
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    ventas_efectivo = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA,
        metodo_pago=MovimientoCaja.MetodoPago.EFECTIVO,
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    ventas_tarjeta = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA,
        metodo_pago=MovimientoCaja.MetodoPago.TARJETA,
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    ventas_qr = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA,
        metodo_pago=MovimientoCaja.MetodoPago.QR,
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    total_ventas = ventas_efectivo + ventas_tarjeta + ventas_qr
    esperado = total_ingresos + ventas_efectivo - total_egresos

    return render(
        request,
        "caja/arqueo.html",
        {
            "caja": caja,
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "total_ventas": total_ventas,
            "ventas_efectivo": ventas_efectivo,
            "ventas_tarjeta": ventas_tarjeta,
            "ventas_qr": ventas_qr,
            "esperado": esperado,
            "movimientos": movs[:20],
        },
    )


@login_required
def movimiento_caja(request):
    caja = get_caja_abierta(request.user)

    if not caja:
        messages.warning(
            request,
            "No tenés una caja abierta. Debés abrir una caja antes de registrar movimientos."
        )
        return redirect("caja:apertura")

    if request.method == "POST":
        form = MovimientoCajaForm(request.POST)
        if form.is_valid():
            try:
                registrar_movimiento(
                    caja=caja,
                    usuario=request.user,
                    tipo=form.cleaned_data["tipo"],
                    monto=form.cleaned_data["monto"],
                    motivo=form.cleaned_data["motivo"],
                    referencia=form.cleaned_data.get("referencia", ""),
                )
                messages.success(request, "Movimiento registrado correctamente.")
                return redirect("caja:arqueo")
            except ValidationError as e:
                messages.error(request, e.message)
        else:
            messages.error(request, "Formulario inválido. Revisá los campos.")
    else:
        form = MovimientoCajaForm()

    return render(
        request,
        "caja/movimiento.html",
        {
            "form": form,
            "caja": caja,
        },
    )


@login_required
def cierre_caja(request):
    caja = get_caja_abierta(request.user)

    if not caja:
        messages.warning(
            request,
            "La caja está cerrada o no existe una caja abierta para cerrar."
        )
        return redirect("caja:apertura")

    movs = caja.movimientos.all()

    total_ingresos = movs.filter(
        tipo=MovimientoCaja.Tipo.INGRESO
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    total_egresos = movs.filter(
        tipo=MovimientoCaja.Tipo.EGRESO
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    ventas_efectivo = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA,
        metodo_pago=MovimientoCaja.MetodoPago.EFECTIVO,
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    ventas_tarjeta = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA,
        metodo_pago=MovimientoCaja.MetodoPago.TARJETA,
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    ventas_qr = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA,
        metodo_pago=MovimientoCaja.MetodoPago.QR,
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    total_ventas = ventas_efectivo + ventas_tarjeta + ventas_qr
    esperado = total_ingresos + ventas_efectivo - total_egresos

    if request.method == "POST":
        form = CierreCajaForm(request.POST)
        if form.is_valid():
            try:
                declarado = form.cleaned_data["monto_cierre"]
                observacion_diferencia = form.cleaned_data.get("observacion_diferencia", "")
                diferencia = declarado - esperado

                cerrar_caja(
                    usuario=request.user,
                    monto_cierre_declarado=declarado,
                    observacion_diferencia=observacion_diferencia,
                )

                messages.success(
                    request,
                    f"La caja se cerró correctamente. Diferencia final: {diferencia}."
                )
                return redirect("caja:historial_cierres")

            except ValidationError as e:
                messages.error(request, e.message)
        else:
            messages.error(request, "Formulario inválido. Revisá el monto de cierre.")
    else:
        form = CierreCajaForm()

    return render(
        request,
        "caja/cierre.html",
        {
            "form": form,
            "caja": caja,
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "total_ventas": total_ventas,
            "ventas_efectivo": ventas_efectivo,
            "ventas_tarjeta": ventas_tarjeta,
            "ventas_qr": ventas_qr,
            "esperado": esperado,
        },
    )


@login_required
def historial_cierres(request):
    sesiones = (
        CajaSesion.objects.select_related("caja", "usuario")
        .filter(estado=CajaSesion.Estado.CERRADA)
        .order_by("-fecha_cierre", "-fecha_apertura")
    )

    if not request.user.is_superuser:
        sesiones = sesiones.filter(usuario=request.user)

    historial = []
    for sesion in sesiones:
        movs = sesion.movimientos.all()

        total_ingresos = movs.filter(
            tipo=MovimientoCaja.Tipo.INGRESO
        ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

        total_egresos = movs.filter(
            tipo=MovimientoCaja.Tipo.EGRESO
        ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

        ventas_efectivo = movs.filter(
            tipo=MovimientoCaja.Tipo.VENTA,
            metodo_pago=MovimientoCaja.MetodoPago.EFECTIVO,
        ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

        ventas_tarjeta = movs.filter(
            tipo=MovimientoCaja.Tipo.VENTA,
            metodo_pago=MovimientoCaja.MetodoPago.TARJETA,
        ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

        ventas_qr = movs.filter(
            tipo=MovimientoCaja.Tipo.VENTA,
            metodo_pago=MovimientoCaja.MetodoPago.QR,
        ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

        total_ventas = ventas_efectivo + ventas_tarjeta + ventas_qr
        esperado = total_ingresos + ventas_efectivo - total_egresos
        declarado = sesion.monto_cierre_declarado or Decimal("0")
        diferencia = declarado - esperado

        historial.append({
            "sesion": sesion,
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "ventas_efectivo": ventas_efectivo,
            "ventas_tarjeta": ventas_tarjeta,
            "ventas_qr": ventas_qr,
            "total_ventas": total_ventas,
            "esperado": esperado,
            "declarado": declarado,
            "diferencia": diferencia,
        })

    return render(
        request,
        "caja/historial_cierres.html",
        {
            "historial": historial,
        },
    )