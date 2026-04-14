from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from apps.caja.services import get_caja_abierta


class BloquearLogoutAdminConCajaAbiertaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_logout_url = reverse("admin:logout")

        if (
            request.user.is_authenticated
            and request.path == admin_logout_url
        ):
            caja_abierta = get_caja_abierta(request.user)

            if caja_abierta:
                messages.error(
                    request,
                    "No podés cerrar sesión desde el panel administrador porque tenés una caja abierta. Primero debés cerrarla."
                )
                return redirect("caja:cierre")

        response = self.get_response(request)
        return response