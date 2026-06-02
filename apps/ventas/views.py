from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render, get_object_or_404

from apps.caja.services import get_caja_abierta
from apps.inventario.models import Stock
from apps.productos.models import Producto
from apps.clientes.models import Cliente

from .models import Venta
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
    return stock_disponible


@login_required
@permission_required("ventas.add_venta", raise_exception=True)
def pos_view(request):
    caja = get_caja_abierta(request.user)

    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()

    productos_qs = (
        Producto.objects.filter(activo=True)
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
        Producto.objects.filter(activo=True)
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
        for p in Producto.objects.filter(activo=True).select_related("categoria")
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

                if Cliente.objects.filter(documento=documento).exists():
                    messages.error(request, "Ya existe un cliente con ese documento.")
                    return redirect("ventas:pos")

                cliente = Cliente.objects.create(
                    nombre=nombre,
                    apellido=apellido,
                    documento=documento,
                    telefono=telefono,
                    email=email,
                    activo=True,
                )
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
                messages.error(request, e.message)
            except Exception as e:
                messages.error(request, f"Error al crear venta: {str(e)}")

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

        stock_valor = _get_stock_disponible(producto.id, stock_map)

        carrito_items.append({
            "producto_id": producto.id,
            "nombre": producto.nombre,
            "categoria": producto.categoria.nombre if producto.categoria else "-",
            "precio": precio,
            "cantidad": cantidad_int,
            "subtotal": subtotal,
            "stock": stock_valor,
        })

    ctx = {
        "caja": caja,
        "productos": productos,
        "stock_map": stock_map,
        "carrito_items": carrito_items,
        "carrito_total": carrito_total,
        "categorias": categorias,
        "clientes": clientes,
        "q": q,
        "categoria_id": categoria_id,
    }
    return render(request, "pos/pos.html", ctx)


@login_required
@permission_required("productos.view_producto", raise_exception=True)
def lista_productos(request):
    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    estado = request.GET.get("estado", "activos").strip()

    productos_qs = Producto.objects.select_related("categoria").order_by(
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
        Producto.objects.select_related("categoria")
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
@permission_required("ventas.view_venta", raise_exception=True)
def ticket_venta(request, venta_id):
    venta = get_object_or_404(
        Venta.objects.select_related("usuario", "caja_sesion", "caja_sesion__caja", "cliente")
        .prefetch_related("detalles", "detalles__producto", "pagos"),
        pk=venta_id,
        estado=Venta.Estado.CONFIRMADA,
    )

    total = venta.total
    iva_10 = total / Decimal("11")
    total_gravado = total - iva_10

    ctx = {
        "venta": venta,
        "comercio_nombre": "Heladería Atenas",
        "comercio_direccion": "Asunción, sobre Eusebio Ayala y Kubicheck",
        "comercio_ruc": "5099245-0",
        "iva_10": iva_10,
        "total_gravado": total_gravado,
    }
    return render(request, "ventas/ticket.html", ctx)