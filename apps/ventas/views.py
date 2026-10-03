from decimal import Decimal, InvalidOperation
import logging

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.caja.services import get_caja_abierta
from apps.inventario.models import Stock
from apps.productos.models import Producto
from apps.clientes.models import Cliente

from .models import Venta
from .services import anular_venta, crear_venta


logger = logging.getLogger(__name__)


CART_SESSION_KEY = "pos_carrito"


def _get_cart(session):
    return session.get(CART_SESSION_KEY, {})


def _save_cart(session, cart):
    session[CART_SESSION_KEY] = cart
    session.modified = True


def _clear_cart(session):
    session[CART_SESSION_KEY] = {}
    session.modified = True


def _parse_decimal(value, default="0"):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _get_stock_disponible(producto_id, stock_map):
    stock_disponible = stock_map.get(producto_id)
    if stock_disponible is None:
        stock_item = Stock.objects.filter(producto_id=producto_id).first()
        stock_disponible = stock_item.cantidad if stock_item else 0
        stock_map[producto_id] = stock_disponible
    return stock_disponible


def _build_cart_state(cart, productos_map, stock_map):
    carrito_items = []
    carrito_total = Decimal("0.00")
    cart_quantities = {}

    for producto_id_str, cantidad in cart.items():
        try:
            producto_id = int(producto_id_str)
            cantidad_int = int(cantidad)
        except (TypeError, ValueError):
            continue

        producto = productos_map.get(producto_id)
        if not producto or cantidad_int <= 0:
            continue

        precio = producto.precio
        subtotal = precio * cantidad_int
        stock_valor = _get_stock_disponible(producto.id, stock_map)
        carrito_total += subtotal
        cart_quantities[producto.id] = cantidad_int

        carrito_items.append({
            "producto_id": producto.id,
            "nombre": producto.nombre,
            "categoria": producto.categoria.nombre if producto.categoria else "-",
            "precio": precio,
            "cantidad": cantidad_int,
            "subtotal": subtotal,
            "stock": stock_valor,
        })

    return {
        "carrito_items": carrito_items,
        "carrito_total": carrito_total,
        "cart_quantities": cart_quantities,
    }


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _cart_action_response(
    request,
    *,
    cart,
    productos_map,
    stock_map,
    success,
    message,
    level="success",
):
    if not _is_ajax(request):
        getattr(messages, level)(request, message)
        return redirect("ventas:pos")

    state = _build_cart_state(cart, productos_map, stock_map)
    payload = {
        "ok": success,
        "message": message,
        "level": level,
        "items": [
            {
                "producto_id": item["producto_id"],
                "nombre": item["nombre"],
                "categoria": item["categoria"],
                "precio": str(item["precio"]),
                "cantidad": item["cantidad"],
                "subtotal": str(item["subtotal"]),
                "stock": int(item["stock"]) if item["stock"] == item["stock"].to_integral_value() else float(item["stock"]),
            }
            for item in state["carrito_items"]
        ],
        "total": str(state["carrito_total"]),
        "cart_quantities": {
            str(producto_id): cantidad
            for producto_id, cantidad in state["cart_quantities"].items()
        },
    }
    return JsonResponse(payload, status=200 if success else 400)


@login_required
@never_cache
@permission_required("ventas.add_venta", raise_exception=True)
def pos_view(request):
    caja = get_caja_abierta(request.user)

    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()

    productos_qs = (
        Producto.objects.filter(
            activo=True,
            tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.PRODUCTO_ELABORADO],
        )
        .select_related("categoria")
        .prefetch_related("stock")
        .order_by("categoria__orden", "categoria__nombre", "nombre")
    )

    if q:
        productos_qs = productos_qs.filter(nombre__icontains=q)

    if categoria_id:
        try:
            productos_qs = productos_qs.filter(categoria_id=int(categoria_id))
        except ValueError:
            pass

    productos = list(productos_qs)

    categorias = (
        Producto.objects.filter(
            activo=True,
            tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.PRODUCTO_ELABORADO],
        )
        .select_related("categoria")
        .values_list("categoria_id", "categoria__nombre")
        .distinct()
        .order_by("categoria__nombre")
    )

    clientes = Cliente.objects.filter(activo=True).order_by("nombre", "apellido")

    stocks = Stock.objects.filter(producto__in=productos).select_related("producto")
    stock_map = {s.producto_id: s.cantidad for s in stocks}

    productos_map = {
        p.id: p
        for p in Producto.objects.filter(
            activo=True,
            tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.PRODUCTO_ELABORADO],
        ).select_related("categoria")
    }

    cart = _get_cart(request.session)

    if request.method == "POST":
        action = request.POST.get("action")

        if action in {"add", "update", "remove", "clear", "confirm"} and not caja:
            messages.error(request, "La caja está cerrada. Debes abrir una caja antes de operar en el POS.")
            return redirect("caja:apertura")

        if action == "add":
            try:
                producto_id = int(request.POST.get("producto_id"))
                cantidad = int(request.POST.get("cantidad", 1))
            except (TypeError, ValueError):
                messages.error(request, "Datos inválidos para agregar al carrito.")
                return redirect("ventas:pos")

            if cantidad <= 0:
                messages.error(request, "La cantidad debe ser mayor a 0.")
                return redirect("ventas:pos")

            producto = productos_map.get(producto_id)
            if not producto:
                messages.error(request, "El producto no existe o no está activo.")
                return redirect("ventas:pos")

            stock_disponible = _get_stock_disponible(producto_id, stock_map)
            cantidad_actual = int(cart.get(str(producto_id), 0))
            nueva_cantidad = cantidad_actual + cantidad

            if nueva_cantidad > stock_disponible:
                if stock_disponible <= 0:
                    messages.error(request, f"'{producto.nombre}' no tiene existencias disponibles.")
                else:
                    messages.warning(request, f"Stock insuficiente para '{producto.nombre}'. Disponible: {stock_disponible}.")
                return redirect("ventas:pos")

            cart[str(producto_id)] = nueva_cantidad
            _save_cart(request.session, cart)
            messages.success(request, f"Se agregó '{producto.nombre}' al carrito.")
            return redirect("ventas:pos")

        elif action == "update":
            try:
                producto_id = int(request.POST.get("producto_id"))
                cantidad = int(request.POST.get("cantidad", 0))
            except (TypeError, ValueError):
                messages.error(request, "Datos inválidos para actualizar el carrito.")
                return redirect("ventas:pos")

            producto = productos_map.get(producto_id)
            if not producto:
                cart.pop(str(producto_id), None)
                _save_cart(request.session, cart)
                messages.error(request, "El producto ya no está disponible.")
                return redirect("ventas:pos")

            stock_disponible = _get_stock_disponible(producto_id, stock_map)

            if cantidad <= 0:
                cart.pop(str(producto_id), None)
                _save_cart(request.session, cart)
                messages.info(request, f"Se quitó '{producto.nombre}' del carrito.")
                return redirect("ventas:pos")

            if cantidad > stock_disponible:
                if stock_disponible <= 0:
                    messages.error(request, f"'{producto.nombre}' ya no tiene existencias disponibles.")
                else:
                    messages.warning(request, f"Stock insuficiente para '{producto.nombre}'. Disponible: {stock_disponible}.")
                return redirect("ventas:pos")

            cart[str(producto_id)] = cantidad
            _save_cart(request.session, cart)
            messages.success(request, f"Se actualizó '{producto.nombre}' en el carrito.")
            return redirect("ventas:pos")

        elif action == "remove":
            try:
                producto_id = int(request.POST.get("producto_id"))
            except (TypeError, ValueError):
                messages.error(request, "Producto inválido.")
                return redirect("ventas:pos")

            producto = productos_map.get(producto_id)
            cart.pop(str(producto_id), None)
            _save_cart(request.session, cart)

            if producto:
                messages.info(request, f"Se quitó '{producto.nombre}' del carrito.")
            else:
                messages.info(request, "Se quitó el producto del carrito.")
            return redirect("ventas:pos")

        elif action == "clear":
            _clear_cart(request.session)
            messages.warning(request, "El carrito fue vaciado.")
            return redirect("ventas:pos")

        elif action == "confirm":
            if not cart:
                messages.error(request, "El carrito está vacío.")
                return redirect("ventas:pos")

            items = []
            for producto_id_str, cantidad in cart.items():
                try:
                    producto_id = int(producto_id_str)
                    cantidad_int = int(cantidad)
                except (TypeError, ValueError):
                    continue

                if cantidad_int <= 0:
                    continue

                items.append({
                    "producto_id": producto_id,
                    "cantidad": cantidad_int,
                })

            if not items:
                messages.error(request, "El carrito no contiene productos válidos.")
                return redirect("ventas:pos")

            cliente = None
            cliente_data = None
            cliente_nuevo = request.POST.get("cliente_nuevo", "").strip()

            if cliente_nuevo == "1":
                nombre = request.POST.get("cliente_nombre", "").strip()
                apellido = request.POST.get("cliente_apellido", "").strip()
                documento = request.POST.get("cliente_documento", "").strip()
                telefono = request.POST.get("cliente_telefono", "").strip()
                email = request.POST.get("cliente_email", "").strip()

                if not nombre or not documento:
                    messages.error(request, "Para alta rápida, nombre y documento son obligatorios.")
                    return redirect("ventas:pos")

                cliente_data = {
                    "nombre": nombre,
                    "apellido": apellido,
                    "documento": documento,
                    "telefono": telefono,
                    "email": email,
                    "activo": True,
                }
            else:
                cliente_id = request.POST.get("cliente_id", "").strip()
                if cliente_id:
                    try:
                        cliente = Cliente.objects.get(pk=int(cliente_id), activo=True)
                    except (ValueError, Cliente.DoesNotExist):
                        messages.error(request, "Cliente inválido.")
                        return redirect("ventas:pos")

            monto_efectivo = _parse_decimal(request.POST.get("monto_efectivo"))
            monto_tarjeta = _parse_decimal(request.POST.get("monto_tarjeta"))
            monto_qr = _parse_decimal(request.POST.get("monto_qr"))

            pagos = []
            if monto_efectivo > 0:
                pagos.append({"metodo_pago": "efectivo", "monto": monto_efectivo})
            if monto_tarjeta > 0:
                pagos.append({"metodo_pago": "tarjeta", "monto": monto_tarjeta})
            if monto_qr > 0:
                pagos.append({"metodo_pago": "qr", "monto": monto_qr})

            if not pagos:
                messages.error(request, "Debés ingresar al menos un monto de pago.")
                return redirect("ventas:pos")

            try:
                venta = crear_venta(
                    usuario=request.user,
                    items=items,
                    pagos=pagos,
                    cliente=cliente,
                    cliente_data=cliente_data,
                )
                _clear_cart(request.session)

                msg = f"Ticket #{venta.numero_ticket:08d} confirmado. Total: {venta.total}"
                if getattr(venta, "vuelto", Decimal("0")) > 0:
                    msg += f" · Vuelto: {venta.vuelto}"
                if hasattr(venta, "pagos_resumen"):
                    msg += f" · {venta.pagos_resumen}"

                messages.success(request, msg)
                return redirect("ventas:ticket", venta_id=venta.id)
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages))
            except Exception:
                logger.exception("Error inesperado al crear una venta")
                messages.error(request, "No se pudo crear la venta. Intentá nuevamente.")

    cart = _get_cart(request.session)

    cart_state = _build_cart_state(cart, productos_map, stock_map)
    stock_remaining_map = {
        producto.id: max(
            _get_stock_disponible(producto.id, stock_map)
            - cart_state["cart_quantities"].get(producto.id, 0),
            0,
        )
        for producto in productos
    }

    ctx = {
        "caja": caja,
        "productos": productos,
        "stock_map": stock_map,
        "stock_remaining_map": stock_remaining_map,
        **cart_state,
        "categorias": categorias,
        "clientes": clientes,
        "q": q,
        "categoria_id": categoria_id,
    }
    return render(request, "pos/pos.html", ctx)


@login_required
@never_cache
@permission_required("ventas.add_venta", raise_exception=True)
@require_POST
def pos_cart_api(request):
    productos_map = {
        producto.id: producto
        for producto in Producto.objects.filter(
            activo=True,
            tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.PRODUCTO_ELABORADO],
        ).select_related("categoria")
    }
    stock_map = {
        stock.producto_id: stock.cantidad
        for stock in Stock.objects.filter(producto_id__in=productos_map)
    }
    cart = _get_cart(request.session)

    if not get_caja_abierta(request.user):
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=False,
            message="La caja está cerrada. Debes abrir una caja antes de operar en el POS.",
            level="error",
        )

    action = request.POST.get("action")
    if action == "clear":
        _clear_cart(request.session)
        return _cart_action_response(
            request,
            cart={},
            productos_map=productos_map,
            stock_map=stock_map,
            success=True,
            message="El carrito fue vaciado.",
            level="warning",
        )

    try:
        producto_id = int(request.POST.get("producto_id"))
    except (TypeError, ValueError):
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=False,
            message="Producto inválido.",
            level="error",
        )

    producto = productos_map.get(producto_id)
    if not producto:
        cart.pop(str(producto_id), None)
        _save_cart(request.session, cart)
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=False,
            message="El producto no existe o ya no está activo.",
            level="error",
        )

    if action == "remove":
        cart.pop(str(producto_id), None)
        _save_cart(request.session, cart)
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=True,
            message=f"Se quitó '{producto.nombre}' del carrito.",
            level="info",
        )

    try:
        cantidad = int(request.POST.get("cantidad", 1 if action == "add" else 0))
    except (TypeError, ValueError):
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=False,
            message="La cantidad ingresada no es válida.",
            level="error",
        )

    if action == "update" and cantidad <= 0:
        cart.pop(str(producto_id), None)
        _save_cart(request.session, cart)
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=True,
            message=f"Se quitó '{producto.nombre}' del carrito.",
            level="info",
        )

    if action not in {"add", "update"} or cantidad <= 0:
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=False,
            message="La acción o la cantidad no es válida.",
            level="error",
        )

    cantidad_actual = int(cart.get(str(producto_id), 0))
    nueva_cantidad = cantidad_actual + cantidad if action == "add" else cantidad
    stock_disponible = _get_stock_disponible(producto_id, stock_map)
    if nueva_cantidad > stock_disponible:
        disponible_para_agregar = max(stock_disponible - cantidad_actual, 0)
        message = (
            f"'{producto.nombre}' no tiene existencias disponibles."
            if stock_disponible <= 0
            else f"Stock insuficiente para '{producto.nombre}'. "
                 f"Disponible para agregar: {disponible_para_agregar}."
        )
        return _cart_action_response(
            request,
            cart=cart,
            productos_map=productos_map,
            stock_map=stock_map,
            success=False,
            message=message,
            level="warning",
        )

    cart[str(producto_id)] = nueva_cantidad
    _save_cart(request.session, cart)
    return _cart_action_response(
        request,
        cart=cart,
        productos_map=productos_map,
        stock_map=stock_map,
        success=True,
        message=(
            f"Se agregó '{producto.nombre}' al carrito."
            if action == "add"
            else f"Se actualizó '{producto.nombre}' en el carrito."
        ),
    )


@login_required
@permission_required("productos.view_producto", raise_exception=True)
def lista_productos(request):
    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    estado = request.GET.get("estado", "activos").strip()

    productos_qs = Producto.objects.filter(
        tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.PRODUCTO_ELABORADO],
    ).select_related("categoria").order_by(
        "categoria__orden",
        "categoria__nombre",
        "nombre",
    )

    if q:
        productos_qs = productos_qs.filter(nombre__icontains=q)

    if categoria_id:
        try:
            productos_qs = productos_qs.filter(categoria_id=int(categoria_id))
        except ValueError:
            pass

    if estado == "activos":
        productos_qs = productos_qs.filter(activo=True)
    elif estado == "inactivos":
        productos_qs = productos_qs.filter(activo=False)

    categorias = (
        Producto.objects.filter(
            tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.PRODUCTO_ELABORADO],
        ).select_related("categoria")
        .values_list("categoria_id", "categoria__nombre")
        .distinct()
        .order_by("categoria__nombre")
    )

    paginator = Paginator(productos_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    stocks = Stock.objects.filter(producto__in=page_obj.object_list).select_related("producto")
    stock_map = {s.producto_id: s.cantidad for s in stocks}

    ctx = {
        "productos": page_obj.object_list,
        "page_obj": page_obj,
        "stock_map": stock_map,
        "categorias": categorias,
        "q": q,
        "categoria_id": categoria_id,
        "estado": estado,
    }
    return render(request, "productos/productos.html", ctx)


@login_required
@never_cache
@permission_required("ventas.view_venta", raise_exception=True)
def ticket_venta(request, venta_id):
    venta = get_object_or_404(
        Venta.objects.select_related("usuario", "caja_sesion", "caja_sesion__caja", "cliente")
        .prefetch_related("detalles", "detalles__producto", "pagos"),
        pk=venta_id,
        estado=Venta.Estado.CONFIRMADA,
    )

    if not request.user.has_perm("ventas.view_global_reports") and venta.usuario_id != request.user.id:
        messages.error(request, "No tenés permisos para ver ese ticket.")
        return redirect("ventas:pos")

    total = venta.total
    iva_10 = (total / Decimal("11")).quantize(Decimal("0.01"))
    total_gravado = total - iva_10

    ctx = {
        "venta": venta,
        "comercio_nombre": settings.COMERCIO_NOMBRE,
        "comercio_direccion": settings.COMERCIO_DIRECCION,
        "comercio_ruc": settings.COMERCIO_RUC,
        "iva_10": iva_10,
        "total_gravado": total_gravado,
    }
    return render(request, "ventas/ticket.html", ctx)


@login_required
@permission_required("ventas.cancel_venta", raise_exception=True)
def anular_venta_view(request, venta_id):
    if request.method != "POST":
        messages.error(request, "Método no permitido para anular una venta.")
        return redirect("reportes:detalle_venta", venta_id=venta_id)

    venta = get_object_or_404(Venta, pk=venta_id)
    try:
        anular_venta(
            venta=venta,
            usuario=request.user,
            motivo=request.POST.get("motivo", ""),
        )
        messages.success(request, f"La venta #{venta.numero_ticket:08d} fue anulada.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("reportes:detalle_venta", venta_id=venta_id)
