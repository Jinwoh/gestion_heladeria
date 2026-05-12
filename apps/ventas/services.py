from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.productos.models import Producto
from apps.inventario.services import restar_stock
from apps.caja.models import MovimientoCaja
from apps.caja.services import get_caja_abierta

from .models import Venta, VentaDetalle, VentaPago


@transaction.atomic
def crear_venta(*, usuario, items, pagos):
    """
    items = [{"producto_id": int, "cantidad": int}, ...]
    pagos = [{"metodo_pago": "efectivo|tarjeta|qr", "monto": Decimal}, ...]
    """
    caja = get_caja_abierta(usuario)
    if not caja:
        raise ValidationError("No hay caja abierta. Abrí caja antes de vender.")

    clean_items = []
    for it in items:
        try:
            pid = int(it.get("producto_id"))
            qty = int(it.get("cantidad"))
        except (TypeError, ValueError):
            raise ValidationError("Hay productos inválidos en la venta.")

        if qty > 0:
            clean_items.append({
                "producto_id": pid,
                "cantidad": qty,
            })

    if not clean_items:
        raise ValidationError("No hay productos con cantidad > 0.")

    productos = Producto.objects.filter(
        id__in=[i["producto_id"] for i in clean_items],
        activo=True,
    )
    productos_map = {p.id: p for p in productos}

    if len(productos_map) != len({i["producto_id"] for i in clean_items}):
        raise ValidationError("Hay productos inválidos o inactivos en la venta.")

    metodos_validos = {
        VentaPago.MetodoPago.EFECTIVO,
        VentaPago.MetodoPago.TARJETA,
        VentaPago.MetodoPago.QR,
    }

    clean_pagos = []
    for p in pagos:
        metodo = p.get("metodo_pago")
        monto = p.get("monto")

        if metodo not in metodos_validos:
            raise ValidationError("Hay métodos de pago inválidos.")

        try:
            monto = Decimal(str(monto))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Hay montos inválidos en los pagos.")

        if monto < 0:
            raise ValidationError("Los montos de pago no pueden ser negativos.")

        if monto > 0:
            clean_pagos.append({
                "metodo_pago": metodo,
                "monto": monto,
            })

    if not clean_pagos:
        raise ValidationError("Debés ingresar al menos un método de pago con monto mayor a 0.")

    total = Decimal("0")

    venta = Venta.objects.create(
        caja_sesion=caja,
        usuario=usuario,
        total=Decimal("0"),
    )

    for it in clean_items:
        producto = productos_map[it["producto_id"]]
        cantidad = it["cantidad"]
        precio = producto.precio
        subtotal = precio * Decimal(cantidad)

        restar_stock(
            producto=producto,
            cantidad=cantidad,
            usuario=usuario,
            motivo=f"Venta {venta.id}",
        )

        VentaDetalle.objects.create(
            venta=venta,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=subtotal,
        )

        total += subtotal

    total_pagos = sum((p["monto"] for p in clean_pagos), Decimal("0"))

    if total_pagos != total:
        raise ValidationError(
            f"La suma de los pagos ({total_pagos}) no coincide con el total de la venta ({total})."
        )

    venta.total = total
    venta.save(update_fields=["total"])

    for pago in clean_pagos:
        pago_obj = VentaPago.objects.create(
            venta=venta,
            metodo_pago=pago["metodo_pago"],
            monto=pago["monto"],
        )

        MovimientoCaja.objects.create(
            caja_sesion=caja,
            tipo=MovimientoCaja.Tipo.VENTA,
            monto=pago["monto"],
            metodo_pago=pago["metodo_pago"],
            referencia=f"venta:{venta.id}:pago:{pago_obj.id}",
            motivo=f"Venta POS - {pago_obj.get_metodo_pago_display()}",
            usuario=usuario,
        )

    return venta
