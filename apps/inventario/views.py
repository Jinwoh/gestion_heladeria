from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import MovimientoStockForm
from .models import Stock
from .services import ajustar_stock, sumar_stock


@login_required
@permission_required("inventario.view_stock", raise_exception=True)
def stock_list(request):
    q = request.GET.get("q", "").strip()
    stocks = Stock.objects.select_related("producto", "producto__categoria").order_by(
        "producto__categoria__nombre", "producto__nombre"
    )
    if q:
        stocks = stocks.filter(
            Q(producto__nombre__icontains=q) | Q(producto__codigo__icontains=q)
        )

    puede_ajustar = request.user.has_perm("inventario.change_stock")
    if request.method == "POST":
        if not puede_ajustar:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        form = MovimientoStockForm(request.POST)
        if form.is_valid():
            try:
                datos = form.cleaned_data
                if datos["accion"] == "entrada":
                    sumar_stock(
                        producto=datos["producto"],
                        cantidad=datos["cantidad"],
                        motivo=datos["motivo"],
                        usuario=request.user,
                    )
                else:
                    ajustar_stock(
                        producto=datos["producto"],
                        nueva_cantidad=datos["cantidad"],
                        motivo=datos["motivo"],
                        usuario=request.user,
                    )
                messages.success(request, "El stock fue actualizado y auditado correctamente.")
                return redirect("inventario:stock")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
    else:
        form = MovimientoStockForm()

    return render(
        request,
        "inventario/stock.html",
        {"stocks": stocks, "form": form, "q": q, "puede_ajustar": puede_ajustar},
    )
