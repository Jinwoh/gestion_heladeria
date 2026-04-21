from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.productos.models import Producto
from apps.inventario.services import restar_stock
from apps.caja.models import MovimientoCaja
from apps.caja.services import get_caja_abierta
from .models import Venta, VentaDetalle


@transaction.atomic
def crear_venta(*, usuario, items, metodo_pago):
    """
    items = [{"producto_id": int, "cantidad": int}, ...]
    """
    caja = get_caja_abierta(usuario)
    if not caja:
        raise ValidationError("No hay caja abierta. Abrí caja antes de vender.")

    metodos_validos = {
        Venta.MetodoPago.EFECTIVO,
        Venta.MetodoPago.TARJETA,
        Venta.MetodoPago.QR,
    }
    if metodo_pago not in metodos_validos:
        raise ValidationError("Método de pago inválido.")

    clean_items = []
    for it in items:
        pid = int(it.get("producto_id"))
        qty = int(it.get("cantidad"))
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

    total = Decimal("0")

    venta = Venta.objects.create(
        caja_sesion=caja,
        usuario=usuario,
        total=Decimal("0"),
        metodo_pago=metodo_pago,
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

    venta.total = total
    venta.save(update_fields=["total"])

    MovimientoCaja.objects.create(
        caja_sesion=caja,
        tipo=MovimientoCaja.Tipo.VENTA,
        monto=total,
        referencia=f"venta:{venta.id}",
        motivo=f"Venta POS - {venta.get_metodo_pago_display()}",
        usuario=usuario,
    )

    return venta