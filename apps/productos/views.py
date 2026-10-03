from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ProductoForm
from .models import Producto


@login_required
@permission_required("productos.view_producto", raise_exception=True)
def productos_view(request):
    q = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    productos = Producto.objects.select_related("categoria", "unidad_medida", "stock")
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q))
    if tipo in Producto.Tipo.values:
        productos = productos.filter(tipo=tipo)
    return render(request, "productos/catalogo.html", {"productos": productos, "q": q, "tipo": tipo, "tipos": Producto.Tipo.choices})


@login_required
@permission_required("productos.add_producto", raise_exception=True)
@require_http_methods(["GET", "POST"])
def producto_crear(request):
    form = ProductoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        producto = form.save()
        messages.success(request, f"Artículo '{producto.nombre}' registrado.")
        return redirect("productos:lista")
    return render(request, "productos/form.html", {"form": form, "titulo": "Nuevo artículo"})


@login_required
@permission_required("productos.change_producto", raise_exception=True)
@require_http_methods(["GET", "POST"])
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, instance=producto)
    if request.method == "POST" and form.is_valid():
        producto = form.save()
        messages.success(request, f"Artículo '{producto.nombre}' actualizado.")
        return redirect("productos:lista")
    return render(request, "productos/form.html", {"form": form, "titulo": "Editar artículo", "producto": producto})


@login_required
@permission_required("productos.change_producto", raise_exception=True)
@require_POST
def producto_toggle(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    producto.activo = not producto.activo
    producto.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, f"Artículo {'activado' if producto.activo else 'desactivado'}.")
    return redirect("productos:lista")
