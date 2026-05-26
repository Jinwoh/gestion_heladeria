from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .models import Cliente


@login_required
@permission_required("clientes.view_cliente", raise_exception=True)
def lista_clientes(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "activos").strip()

    clientes_qs = Cliente.objects.all().order_by("nombre", "apellido")

    if q:
        clientes_qs = clientes_qs.filter(
            nombre__icontains=q
        ) | clientes_qs.filter(
            apellido__icontains=q
        ) | clientes_qs.filter(
            documento__icontains=q
        )

    if estado == "activos":
        clientes_qs = clientes_qs.filter(activo=True)
    elif estado == "inactivos":
        clientes_qs = clientes_qs.filter(activo=False)

    paginator = Paginator(clientes_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "clientes/lista.html",
        {
            "page_obj": page_obj,
            "clientes": page_obj.object_list,
            "q": q,
            "estado": estado,
        },
    )