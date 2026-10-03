import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.utils.dateparse import parse_date

from apps.productos.models import Producto, UnidadMedida

from .forms import AjusteStockForm, DetalleOrdenFormSet, OrdenCompraForm, ProveedorForm
from .models import MovimientoStock, OrdenCompra, Proveedor, RecepcionCompra, Stock
from .services import ajustar_stock, cancelar_orden, emitir_orden, registrar_recepcion


@login_required
@permission_required("inventario.view_stock", raise_exception=True)
@require_GET
def stock_list(request):
    q = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    estado = request.GET.get("estado", "").strip()
    ultimo_movimiento = MovimientoStock.objects.filter(producto_id=OuterRef("producto_id")).order_by("-creado_en")
    stocks = Stock.objects.select_related("producto", "producto__categoria", "producto__unidad_medida").annotate(
        ultimo_movimiento_fecha=Subquery(ultimo_movimiento.values("creado_en")[:1]),
        ultimo_movimiento_tipo=Subquery(ultimo_movimiento.values("tipo")[:1]),
    ).order_by("producto__tipo", "producto__categoria__nombre", "producto__nombre")
    if q:
        stocks = stocks.filter(Q(producto__nombre__icontains=q) | Q(producto__codigo__icontains=q))
    if tipo in Producto.Tipo.values:
        stocks = stocks.filter(producto__tipo=tipo)
    if estado == "sin_stock":
        stocks = stocks.filter(cantidad=0)
    elif estado == "bajo":
        stocks = stocks.filter(cantidad__gt=0, cantidad__lte=models.F("producto__stock_minimo"))
    elif estado == "normal":
        stocks = stocks.filter(cantidad__gt=models.F("producto__stock_minimo"))
    return render(request, "inventario/stock.html", {"stocks": stocks, "q": q, "tipo": tipo, "estado": estado, "tipos": Producto.Tipo.choices})


@login_required
@permission_required("inventario.change_stock", raise_exception=True)
@require_http_methods(["GET", "POST"])
def stock_movement(request):
    form = AjusteStockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            ajustar_stock(producto=form.cleaned_data["producto"], nueva_cantidad=form.cleaned_data["cantidad"], motivo=form.cleaned_data["motivo"], usuario=request.user)
            messages.success(request, "El ajuste fue registrado y auditado correctamente.")
            return redirect("inventario:movimiento")
        except ValidationError as exc:
            form.add_error(None, exc)
    productos = Producto.objects.filter(activo=True).select_related("unidad_medida", "stock")
    datos = {
        str(producto.pk): {"stock": str(getattr(producto, "stock", None).cantidad if hasattr(producto, "stock") else 0), "unidad": producto.unidad_medida.abreviatura}
        for producto in productos
    }
    return render(request, "inventario/movimiento.html", {"form": form, "stock_por_producto": datos})


@login_required
@permission_required("inventario.view_movimientostock", raise_exception=True)
def movimientos_list(request):
    q = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    movimientos = MovimientoStock.objects.select_related("producto", "producto__unidad_medida", "usuario").order_by("-creado_en", "-pk")
    if q:
        movimientos = movimientos.filter(Q(producto__nombre__icontains=q) | Q(motivo__icontains=q))
    if tipo in MovimientoStock.Tipo.values:
        movimientos = movimientos.filter(tipo=tipo)
    return render(request, "inventario/movimientos.html", {"movimientos": movimientos[:300], "q": q, "tipo": tipo, "tipos": MovimientoStock.Tipo.choices})


@login_required
@permission_required("inventario.view_proveedor", raise_exception=True)
def proveedores_list(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "activos")
    proveedores = Proveedor.objects.annotate(ordenes_count=Count("ordenes_compra"))
    if q:
        proveedores = proveedores.filter(Q(razon_social__icontains=q) | Q(ruc__icontains=q) | Q(persona_contacto__icontains=q))
    if estado == "activos":
        proveedores = proveedores.filter(activo=True)
    elif estado == "inactivos":
        proveedores = proveedores.filter(activo=False)
    return render(request, "inventario/proveedores/lista.html", {"proveedores": proveedores, "q": q, "estado": estado})


@login_required
@permission_required("inventario.add_proveedor", raise_exception=True)
@require_http_methods(["GET", "POST"])
def proveedor_crear(request):
    form = ProveedorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        proveedor = form.save()
        messages.success(request, f"Proveedor '{proveedor.razon_social}' registrado.")
        return redirect("inventario:proveedores")
    return render(request, "inventario/proveedores/form.html", {"form": form, "titulo": "Nuevo proveedor"})


@login_required
@permission_required("inventario.change_proveedor", raise_exception=True)
@require_http_methods(["GET", "POST"])
def proveedor_editar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    form = ProveedorForm(request.POST or None, instance=proveedor)
    if request.method == "POST" and form.is_valid():
        proveedor = form.save()
        messages.success(request, f"Proveedor '{proveedor.razon_social}' actualizado.")
        return redirect("inventario:proveedores")
    return render(request, "inventario/proveedores/form.html", {"form": form, "titulo": "Editar proveedor", "proveedor": proveedor})


@login_required
@permission_required("inventario.change_proveedor", raise_exception=True)
@require_POST
def proveedor_toggle(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    proveedor.activo = not proveedor.activo
    proveedor.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, f"Proveedor {'activado' if proveedor.activo else 'desactivado'} correctamente.")
    return redirect("inventario:proveedores")


@login_required
@permission_required("inventario.view_ordencompra", raise_exception=True)
def ordenes_list(request):
    ordenes = OrdenCompra.objects.select_related("proveedor", "creado_por").annotate(productos_count=Count("detalles"))
    numero = request.GET.get("numero", "").strip().upper().replace("OC-", "")
    proveedor = request.GET.get("proveedor", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    estado = request.GET.get("estado", "").strip()
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    fecha_hasta = request.GET.get("fecha_hasta", "").strip()
    if numero.isdigit():
        ordenes = ordenes.filter(numero=int(numero))
    if proveedor.isdigit():
        ordenes = ordenes.filter(proveedor_id=int(proveedor))
    if tipo in {Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.INSUMO}:
        ordenes = ordenes.filter(tipo=tipo)
    if estado in OrdenCompra.Estado.values:
        ordenes = ordenes.filter(estado=estado)
    if fecha_desde and parse_date(fecha_desde):
        ordenes = ordenes.filter(fecha__gte=fecha_desde)
    if fecha_hasta and parse_date(fecha_hasta):
        ordenes = ordenes.filter(fecha__lte=fecha_hasta)
    return render(request, "inventario/compras/lista.html", {
        "ordenes": ordenes, "proveedores": Proveedor.objects.order_by("razon_social"), "tipos": OrdenCompra._meta.get_field("tipo").choices, "estados": OrdenCompra.Estado.choices,
        "filtros": request.GET,
    })


def _articulos_json():
    return {
        str(producto.pk): {"tipo": producto.tipo, "unidad_id": producto.unidad_medida_id, "unidad": producto.unidad_medida.abreviatura, "ultimo_costo": str(producto.ultimo_costo or "")}
        for producto in Producto.objects.filter(activo=True, tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.INSUMO]).select_related("unidad_medida")
    }


@login_required
@permission_required("inventario.add_ordencompra", raise_exception=True)
@require_http_methods(["GET", "POST"])
def orden_crear(request):
    tipo = request.POST.get("tipo") if request.method == "POST" else None
    form = OrdenCompraForm(request.POST or None)
    orden = OrdenCompra(creado_por=request.user)
    formset = DetalleOrdenFormSet(request.POST or None, instance=orden, tipo_orden=tipo)
    if request.method == "POST" and form.is_valid():
        tipo = form.cleaned_data["tipo"]
        formset = DetalleOrdenFormSet(request.POST, instance=orden, tipo_orden=tipo)
        if formset.is_valid():
            with transaction.atomic():
                orden = form.save(commit=False)
                orden.creado_por = request.user
                orden.save()
                formset.instance = orden
                detalles = formset.save(commit=False)
                for detalle in detalles:
                    detalle.orden_compra = orden
                    detalle.full_clean()
                    detalle.save()
                for eliminado in formset.deleted_objects:
                    eliminado.delete()
            messages.success(request, f"{orden.numero_formateado} creada en borrador. El stock no fue modificado.")
            return redirect("inventario:orden_detalle", pk=orden.pk)
    return render(request, "inventario/compras/form.html", {"form": form, "formset": formset, "titulo": "Nueva orden de compra", "articulos_json": _articulos_json()})


@login_required
@permission_required("inventario.change_ordencompra", raise_exception=True)
@require_http_methods(["GET", "POST"])
def orden_editar(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    if not orden.puede_editarse:
        messages.error(request, "Solo las órdenes en borrador pueden editarse.")
        return redirect("inventario:orden_detalle", pk=pk)
    tipo = request.POST.get("tipo", orden.tipo)
    form = OrdenCompraForm(request.POST or None, instance=orden)
    formset = DetalleOrdenFormSet(request.POST or None, instance=orden, tipo_orden=tipo)
    if request.method == "POST" and form.is_valid():
        tipo = form.cleaned_data["tipo"]
        formset = DetalleOrdenFormSet(request.POST, instance=orden, tipo_orden=tipo)
        if formset.is_valid():
            with transaction.atomic():
                orden = form.save()
                formset.instance = orden
                detalles = formset.save(commit=False)
                for detalle in detalles:
                    detalle.orden_compra = orden
                    detalle.full_clean()
                    detalle.save()
                for eliminado in formset.deleted_objects:
                    eliminado.delete()
            messages.success(request, f"{orden.numero_formateado} actualizada.")
            return redirect("inventario:orden_detalle", pk=orden.pk)
    return render(request, "inventario/compras/form.html", {"form": form, "formset": formset, "titulo": f"Editar {orden.numero_formateado}", "orden": orden, "articulos_json": _articulos_json()})


@login_required
@permission_required("inventario.view_ordencompra", raise_exception=True)
def orden_detalle(request, pk):
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor", "creado_por").prefetch_related("detalles__producto", "detalles__unidad_medida", "recepciones__usuario_receptor"), pk=pk)
    return render(request, "inventario/compras/detalle.html", {"orden": orden})


@login_required
@permission_required("inventario.emitir_ordencompra", raise_exception=True)
@require_POST
def orden_emitir(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    try:
        emitir_orden(orden, usuario=request.user)
        messages.success(request, f"{orden.numero_formateado} fue emitida. El stock aún no cambió.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("inventario:orden_detalle", pk=pk)


@login_required
@permission_required("inventario.cancelar_ordencompra", raise_exception=True)
@require_POST
def orden_cancelar(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    try:
        cancelar_orden(orden, usuario=request.user)
        messages.success(request, f"{orden.numero_formateado} fue cancelada.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("inventario:orden_detalle", pk=pk)


@login_required
@permission_required("inventario.recibir_ordencompra", raise_exception=True)
@require_http_methods(["GET", "POST"])
def orden_recibir(request, pk):
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor"), pk=pk)
    if not orden.puede_recibirse:
        messages.error(request, "La orden no está disponible para recepción.")
        return redirect("inventario:orden_detalle", pk=pk)
    detalles = list(orden.detalles.select_related("producto", "unidad_medida").prefetch_related("detalles_recepcion"))
    token = request.POST.get("clave_idempotencia") or str(uuid.uuid4())
    if request.method == "POST":
        cantidades = {detalle.pk: request.POST.get(f"detalle_{detalle.pk}", "0") for detalle in detalles}
        try:
            recepcion, creada = registrar_recepcion(orden=orden, cantidades=cantidades, usuario=request.user, clave_idempotencia=token, observacion=request.POST.get("observacion", ""))
            messages.success(request, "Recepción confirmada; stock y movimientos actualizados." if creada else "La recepción ya había sido procesada; no se duplicó el stock.")
            return redirect("inventario:recepcion_detalle", pk=recepcion.pk)
        except (ValidationError, ValueError) as exc:
            mensajes = exc.messages if isinstance(exc, ValidationError) else ["La clave de operación no es válida."]
            messages.error(request, "; ".join(mensajes))
    return render(request, "inventario/compras/recibir.html", {"orden": orden, "detalles": detalles, "clave_idempotencia": token})


@login_required
@permission_required("inventario.view_recepcioncompra", raise_exception=True)
def recepciones_list(request):
    recepciones = RecepcionCompra.objects.select_related("orden_compra", "orden_compra__proveedor", "usuario_receptor").annotate(lineas=Count("detalles"))
    pendientes = OrdenCompra.objects.filter(
        estado__in=[OrdenCompra.Estado.EMITIDA, OrdenCompra.Estado.PARCIALMENTE_RECIBIDA],
    ).select_related("proveedor").order_by("fecha", "numero")
    return render(request, "inventario/compras/recepciones.html", {"recepciones": recepciones, "ordenes_pendientes": pendientes})


@login_required
@permission_required("inventario.view_recepcioncompra", raise_exception=True)
def recepcion_detalle(request, pk):
    recepcion = get_object_or_404(RecepcionCompra.objects.select_related("orden_compra", "orden_compra__proveedor", "usuario_receptor").prefetch_related("detalles__detalle_orden__producto", "detalles__detalle_orden__unidad_medida", "detalles__movimiento_stock"), pk=pk)
    return render(request, "inventario/compras/recepcion_detalle.html", {"recepcion": recepcion})
