from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from apps.productos.models import Producto
from apps.inventario.models import Stock
from apps.caja.services import get_caja_abierta
from .services import crear_venta

@login_required
def pos_view(request):
    caja = get_caja_abierta(request.user)

    # Productos activos + stock (si existe)
    productos = (
        Producto.objects.filter(activo=True)
        .select_related("categoria")
        .prefetch_related("stock")
        .order_by("categoria__orden", "categoria__nombre", "nombre")
    )

    # Map stock por producto (para mostrar)
    stocks = Stock.objects.filter(producto__in=productos).select_related("producto")
    stock_map = {s.producto_id: s.cantidad for s in stocks}

    if request.method == "POST":
        if not caja:
            messages.error(request, "No hay caja abierta. Abrí caja antes de vender.")
            return redirect("caja:apertura")

        # Arrays del form
        pids = request.POST.getlist("producto_id")
        qtys = request.POST.getlist("cantidad")

        items = []
        for pid, qty in zip(pids, qtys):
            try:
                pid_int = int(pid)
                qty_int = int(qty or 0)
            except ValueError:
                continue
            items.append({"producto_id": pid_int, "cantidad": qty_int})

        try:
            venta = crear_venta(usuario=request.user, items=items)
            messages.success(request, f"Venta #{venta.id} confirmada. Total: {venta.total}")
            return redirect("ventas:pos")
        except ValidationError as e:
            messages.error(request, e.message)
        except Exception as e:
            # fallback para errores inesperados
            messages.error(request, f"Error al crear venta: {str(e)}")

    ctx = {
        "caja": caja,
        "productos": productos,
        "stock_map": stock_map,
    }
    return render(request, "pos/pos.html", ctx)