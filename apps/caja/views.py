from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from apps.caja.models import CajaSesion

from .forms import AperturaCajaForm, CierreCajaForm, MovimientoCajaForm
from .services import (
    abrir_caja,
    cerrar_caja,
    get_caja_abierta,
    registrar_movimiento,
    resumen_caja,
)


@login_required
@permission_required("caja.add_cajasesion", raise_exception=True)
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
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
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
@permission_required("caja.view_cajasesion", raise_exception=True)
def arqueo_caja(request):
    caja = get_caja_abierta(request.user)

    if not caja:
        messages.warning(
            request,
            "La caja está cerrada. Debes abrir una caja para continuar."
        )
        return redirect("caja:apertura")

    movs = caja.movimientos.all()
    resumen = resumen_caja(caja)

    return render(
        request,
        "caja/arqueo.html",
        {
            "caja": caja,
            **resumen,
            "movimientos": movs[:20],
        },
    )


@login_required
@permission_required("caja.add_movimientocaja", raise_exception=True)
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
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
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
@permission_required("caja.change_cajasesion", raise_exception=True)
def cierre_caja(request):
    caja = get_caja_abierta(request.user)

    if not caja:
        messages.warning(
            request,
            "La caja está cerrada o no existe una caja abierta para cerrar."
        )
        return redirect("caja:apertura")

    resumen = resumen_caja(caja)
    esperado = resumen["esperado"]

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

            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
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
            **resumen,
        },
    )


@login_required
@permission_required("caja.view_cajasesion", raise_exception=True)
def historial_cierres(request):
    sesiones = (
        CajaSesion.objects.select_related("caja", "usuario")
        .filter(estado=CajaSesion.Estado.CERRADA)
        .order_by("-fecha_cierre", "-fecha_apertura")
    )

    if not request.user.is_superuser and not request.user.has_perm("ventas.view_global_reports"):
        sesiones = sesiones.filter(usuario=request.user)

    page_obj = Paginator(sesiones, 25).get_page(request.GET.get("page"))
    historial = []
    for sesion in page_obj.object_list:
        resumen = resumen_caja(sesion)
        esperado = resumen["esperado"]
        declarado = sesion.monto_cierre_declarado or Decimal("0")
        diferencia = declarado - esperado

        historial.append({
            "sesion": sesion,
            **resumen,
            "declarado": declarado,
            "diferencia": diferencia,
        })

    return render(
        request,
        "caja/historial_cierres.html",
        {
            "historial": historial,
            "page_obj": page_obj,
        },
    )
