from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.productos.models import Producto
from apps.inventario.services import restar_stock
from apps.caja.models import MovimientoCaja
from apps.caja.services import get_caja_abierta

from .models import Venta, VentaDetalle


@transaction.atomic
def crear_venta(*, usuario, items: list[dict]) -> Venta:
    """
    items = [{"producto_id": int, "cantidad": int}, ...]
    """
    caja = get_caja_abierta(usuario)
    if not caja:
        raise ValidationError("No hay caja abierta. Abrí caja antes de vender.")

    # Limpiar items inválidos
    clean_items = []
    for it in items:
        pid = int(it.get("producto_id"))
        qty = int(it.get("cantidad"))
        if qty > 0:
            clean_items.append({"producto_id": pid, "cantidad": qty})

    if not clean_items:
        raise ValidationError("No hay productos con cantidad > 0.")

    # Traer productos de una vez
    productos = Producto.objects.filter(id__in=[i["producto_id"] for i in clean_items], activo=True)
    productos_map = {p.id: p for p in productos}

    if len(productos_map) != len({i["producto_id"] for i in clean_items}):
        raise ValidationError("Hay productos inválidos o inactivos en la venta.")

    venta = Venta.objects.create(caja_sesion=caja, usuario=usuario, total=0)

    total = Decimal("0")

    # Crear detalles + descontar stock
    for it in clean_items:
        producto = productos_map[it["producto_id"]]
        cantidad = it["cantidad"]
        precio = producto.precio
        subtotal = (precio * Decimal(cantidad))

        # Descontar stock (valida no negativo)
        restar_stock(producto=producto, cantidad=cantidad, usuario=usuario, motivo=f"Venta {venta.id}")

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

    # Movimiento de caja (VENTA)
    MovimientoCaja.objects.create(
    caja_sesion=caja,
    tipo=MovimientoCaja.Tipo.VENTA,
    monto=total,
    referencia=f"venta:{venta.id}",
    motivo="Venta POS",
    usuario=usuario,
    )

    return venta