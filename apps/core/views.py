from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.caja.services import get_caja_abierta


@login_required
def home_view(request):
    return render(request, "core/home.html")


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