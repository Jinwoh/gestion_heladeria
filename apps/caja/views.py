from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

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
        messages.warning(request, "No hay caja abierta. Abrí una caja para comenzar.")
        return redirect("caja:apertura")

    return render(request, "caja/arqueo.html", {"caja": caja})


@login_required
def cierre_caja(request):
    caja = get_caja_abierta(request.user)
    if not caja:
        messages.warning(request, "No hay caja abierta para cerrar.")
        return redirect("caja:apertura")

    if request.method == "POST":
        form = CierreCajaForm(request.POST)
        if form.is_valid():
            try:
                cerrar_caja(usuario=request.user, monto_cierre_declarado=form.cleaned_data["monto_cierre"])
                messages.success(request, "Caja cerrada correctamente.")
                return redirect("reportes:reporte_dia")
            except ValidationError as e:
                messages.error(request, e.message)
    else:
        form = CierreCajaForm()

    return render(request, "caja/cierre.html", {"form": form, "caja": caja})