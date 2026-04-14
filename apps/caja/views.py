from decimal import Decimal
from django.db.models import Sum
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from apps.caja.models import MovimientoCaja

from .forms import AperturaCajaForm, CierreCajaForm
from .services import abrir_caja, cerrar_caja, get_caja_abierta


@login_required
def apertura_caja(request):
    caja = get_caja_abierta(request.user)

    if request.method == "POST":
        form = AperturaCajaForm(request.POST)
        if form.is_valid():
            try:
                abrir_caja(
                    usuario=request.user,
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
        form = AperturaCajaForm(initial={"monto_apertura": 0})

    return render(request, "caja/apertura.html", {"form": form, "caja": caja})


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

    total_ventas = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    # OJO: la apertura ya se registra como INGRESO en services.py
    esperado = total_ingresos + total_ventas - total_egresos

    return render(
        request,
        "caja/arqueo.html",
        {
            "caja": caja,
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "total_ventas": total_ventas,
            "esperado": esperado,
            "movimientos": movs[:20],
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

    total_ventas = movs.filter(
        tipo=MovimientoCaja.Tipo.VENTA
    ).aggregate(s=Sum("monto"))["s"] or Decimal("0")

    # OJO: la apertura ya se registra como INGRESO en services.py
    esperado = total_ingresos + total_ventas - total_egresos

    if request.method == "POST":
        form = CierreCajaForm(request.POST)
        if form.is_valid():
            try:
                declarado = form.cleaned_data["monto_cierre"]
                diferencia = declarado - esperado

                cerrar_caja(
                    usuario=request.user,
                    monto_cierre_declarado=declarado,
                )

                messages.success(
                    request,
                    f"La caja se cerró correctamente. Diferencia final: {diferencia}."
                )
                return redirect("caja:apertura")

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
            "esperado": esperado,
        },
    )