from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.caja.services import get_caja_abierta
from .dashboard import construir_dashboard
from .forms import MetaMensualForm
from .models import ConfiguracionDashboard


@login_required
def home_view(request):
    periodo = request.GET.get("period", "6m")
    dashboard = construir_dashboard(usuario=request.user, periodo=periodo)
    return render(request, "core/home.html", {"dashboard": dashboard})


@login_required
@permission_required("core.change_configuraciondashboard", raise_exception=True)
@require_POST
def actualizar_meta_dashboard(request):
    configuracion = ConfiguracionDashboard.objects.filter(pk=1).first()
    form = MetaMensualForm(request.POST, instance=configuracion)
    periodo = request.POST.get("period", "6m")
    if periodo not in {"6m", "12m", "ytd"}:
        periodo = "6m"

    if form.is_valid():
        configuracion = form.save(commit=False)
        configuracion.actualizada_por = request.user
        configuracion.save()
        messages.success(request, "La meta mensual fue actualizada correctamente.")
    else:
        error = next(iter(form.errors.values()))[0]
        messages.error(request, f"No se pudo actualizar la meta: {error}")

    return redirect(f'{reverse("home")}?period={periodo}')


@login_required
def logout_view(request):
    if request.method != "POST":
        messages.error(request, "Método no permitido para cerrar sesión.")
        return redirect("home")

    caja_abierta = get_caja_abierta(request.user)

    if caja_abierta:
        messages.error(
            request,
            "No podés cerrar sesión porque tenés una caja abierta. Primero debés cerrarla."
        )
        return redirect("caja:cierre")

    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect("login")
