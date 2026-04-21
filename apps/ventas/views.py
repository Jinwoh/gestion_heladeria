from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from apps.caja.services import get_caja_abierta
from apps.inventario.models import Stock
from apps.productos.models import Producto
from .services import crear_venta


CART_SESSION_KEY = "pos_carrito"


def _get_cart(session):
    return session.get(CART_SESSION_KEY, {})


def _save_cart(session, cart):
    session[CART_SESSION_KEY] = cart
    session.modified = True


def _clear_cart(session):
    session[CART_SESSION_KEY] = {}
    session.modified = True


@login_required
def pos_view(request):
    caja = get_caja_abierta(request.user)

    productos = (
        Producto.objects.filter(activo=True)
        .select_related("categoria")
        .prefetch_related("stock")
        .order_by("categoria__orden", "categoria__nombre", "nombre")
    )

    stocks = Stock.objects.filter(producto__in=productos).select_related("producto")
    stock_map = {s.producto_id: s.cantidad for s in stocks}

    productos_map = {p.id: p for p in productos}
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

            stock_disponible = stock_map.get(producto_id, 0)
            cantidad_actual = int(cart.get(str(producto_id), 0))
            nueva_cantidad = cantidad_actual + cantidad

            if nueva_cantidad > stock_disponible:
                if stock_disponible <= 0:
                    messages.error(
                        request,
                        f"'{producto.nombre}' no tiene existencias disponibles."
                    )
                else:
                    messages.warning(
                        request,
                        f"Stock insuficiente para '{producto.nombre}'. Disponible: {stock_disponible}."
                    )
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

            stock_disponible = stock_map.get(producto_id, 0)

            if cantidad <= 0:
                cart.pop(str(producto_id), None)
                _save_cart(request.session, cart)
                messages.info(request, f"Se quitó '{producto.nombre}' del carrito.")
                return redirect("ventas:pos")

            if cantidad > stock_disponible:
                if stock_disponible <= 0:
                    messages.error(
                        request,
                        f"'{producto.nombre}' ya no tiene existencias disponibles."
                    )
                else:
                    messages.warning(
                        request,
                        f"Stock insuficiente para '{producto.nombre}'. Disponible: {stock_disponible}."
                    )
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

                items.append(
                    {
                        "producto_id": producto_id,
                        "cantidad": cantidad_int,
                    }
                )

            if not items:
                messages.error(request, "El carrito no contiene productos válidos.")
                return redirect("ventas:pos")

            metodo_pago = request.POST.get("metodo_pago", "efectivo")
            metodos_validos = {"efectivo", "tarjeta", "qr"}

            if metodo_pago not in metodos_validos:
                messages.error(request, "Método de pago inválido.")
                return redirect("ventas:pos")

            try:
                venta = crear_venta(
                    usuario=request.user,
                    items=items,
                    metodo_pago=metodo_pago,
                )
                _clear_cart(request.session)
                messages.success(
                    request,
                    f"Venta #{venta.id} confirmada. Total: {venta.total} · Método: {venta.get_metodo_pago_display()}"
                )
                return redirect("ventas:pos")
            except ValidationError as e:
                messages.error(request, e.message)
            except Exception as e:
                messages.error(request, f"Error al crear venta: {str(e)}")

    # Releer carrito después de posibles cambios
    cart = _get_cart(request.session)

    carrito_items = []
    carrito_total = Decimal("0.00")

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
        carrito_total += subtotal

        carrito_items.append(
            {
                "producto_id": producto.id,
                "nombre": producto.nombre,
                "categoria": producto.categoria.nombre if producto.categoria else "-",
                "precio": precio,
                "cantidad": cantidad_int,
                "subtotal": subtotal,
                "stock": stock_map.get(producto.id, 0),
            }
        )

    ctx = {
        "caja": caja,
        "productos": productos,
        "stock_map": stock_map,
        "carrito_items": carrito_items,
        "carrito_total": carrito_total,
    }
    return render(request, "pos/pos.html", ctx)


