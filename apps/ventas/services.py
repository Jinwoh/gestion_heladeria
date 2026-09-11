from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.productos.models import Producto
from apps.inventario.services import restar_stock, sumar_stock
from apps.caja.models import CajaSesion, MovimientoCaja

from .models import Venta, VentaDetalle, VentaPago


CENTAVO = Decimal("0.01")


def _monto_valido(value) -> Decimal:
    try:
        monto = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Hay montos inválidos en los pagos.")
    if not monto.is_finite() or monto < 0 or monto != monto.quantize(CENTAVO):
        raise ValidationError("Los pagos deben ser importes positivos con hasta dos decimales.")
    return monto


@transaction.atomic
def crear_venta(*, usuario, items, pagos, cliente=None, cliente_data=None):
    """
    items = [{"producto_id": int, "cantidad": int}, ...]
    pagos = [{"metodo_pago": "efectivo|tarjeta|qr", "monto": Decimal}, ...]
    """
    caja = (
        CajaSesion.objects.select_for_update()
        .select_related("caja")
        .filter(usuario=usuario, estado=CajaSesion.Estado.ABIERTA)
        .first()
    )
    if not caja:
        raise ValidationError("No hay caja abierta. Abrí caja antes de vender.")

    cantidades = defaultdict(int)
    for it in items:
        try:
            pid = int(it.get("producto_id"))
            qty = int(it.get("cantidad"))
        except (TypeError, ValueError):
            raise ValidationError("Hay productos inválidos en la venta.")

        if qty > 0:
            cantidades[pid] += qty

    clean_items = [
        {"producto_id": producto_id, "cantidad": cantidad}
        for producto_id, cantidad in cantidades.items()
    ]

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

    pagos_por_metodo = defaultdict(lambda: Decimal("0"))
    for p in pagos:
        metodo = p.get("metodo_pago")
        monto = p.get("monto")

        if metodo not in metodos_validos:
            raise ValidationError("Hay métodos de pago inválidos.")

        monto = _monto_valido(monto)
        if monto > 0:
            pagos_por_metodo[metodo] += monto

    clean_pagos = [
        {"metodo_pago": metodo, "monto": monto}
        for metodo, monto in pagos_por_metodo.items()
    ]

    if not clean_pagos:
        raise ValidationError("Debés ingresar al menos un método de pago con monto mayor a 0.")

    total = Decimal("0")

    if cliente is not None and cliente_data:
        raise ValidationError("No se puede indicar un cliente existente y uno nuevo a la vez.")

    if cliente_data:
        from apps.clientes.models import Cliente

        cliente = Cliente(**cliente_data)
        cliente.full_clean()
        cliente.save()

    venta = Venta.objects.create(
        caja_sesion=caja,
        usuario=usuario,
        cliente=cliente,
        total=Decimal("0"),
        vuelto=Decimal("0"),
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
    monto_efectivo = sum(
        (p["monto"] for p in clean_pagos if p["metodo_pago"] == VentaPago.MetodoPago.EFECTIVO),
        Decimal("0"),
    )
    monto_no_efectivo = total_pagos - monto_efectivo

    if total_pagos < total:
        raise ValidationError(
            f"La suma de los pagos ({total_pagos}) no alcanza el total de la venta ({total})."
        )

    if monto_no_efectivo > total:
        raise ValidationError("La suma de tarjeta y QR no puede superar el total de la venta.")

    saldo_a_cubrir_con_efectivo = total - monto_no_efectivo

    if monto_efectivo < saldo_a_cubrir_con_efectivo:
        raise ValidationError("El monto en efectivo no alcanza para cubrir el saldo restante.")

    vuelto = monto_efectivo - saldo_a_cubrir_con_efectivo

    venta.total = total
    venta.vuelto = vuelto
    venta.save(update_fields=["total", "vuelto"])

    for pago in clean_pagos:
        monto_recibido = pago["monto"]
        monto_aplicado = monto_recibido
        if pago["metodo_pago"] == VentaPago.MetodoPago.EFECTIVO:
            monto_aplicado = saldo_a_cubrir_con_efectivo

        if monto_aplicado <= 0:
            raise ValidationError("No se puede recibir efectivo si otros medios ya cubren la venta.")

        pago_obj = VentaPago.objects.create(
            venta=venta,
            metodo_pago=pago["metodo_pago"],
            monto=monto_aplicado,
            monto_recibido=monto_recibido,
        )

        MovimientoCaja.objects.create(
            caja_sesion=caja,
            tipo=MovimientoCaja.Tipo.VENTA,
            monto=monto_aplicado,
            metodo_pago=pago["metodo_pago"],
            referencia=f"venta:{venta.id}:pago:{pago_obj.id}",
            motivo=f"Venta POS - {pago_obj.get_metodo_pago_display()}",
            usuario=usuario,
        )

    return venta


@transaction.atomic
def anular_venta(*, venta: Venta, usuario, motivo: str) -> Venta:
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("Debés indicar el motivo de la anulación.")

    venta = (
        Venta.objects.select_for_update()
        .select_related("caja_sesion")
        .prefetch_related("detalles__producto", "pagos")
        .get(pk=venta.pk)
    )
    if venta.estado != Venta.Estado.CONFIRMADA:
        raise ValidationError("La venta ya fue anulada.")
    caja_sesion = CajaSesion.objects.select_for_update().get(pk=venta.caja_sesion_id)
    if caja_sesion.estado != CajaSesion.Estado.ABIERTA:
        raise ValidationError("Solo se puede anular una venta mientras su caja permanece abierta.")

    for detalle in venta.detalles.all():
        sumar_stock(
            producto=detalle.producto,
            cantidad=detalle.cantidad,
            usuario=usuario,
            motivo=f"Anulación de venta {venta.id}",
        )

    for pago in venta.pagos.all():
        MovimientoCaja.objects.create(
            caja_sesion=caja_sesion,
            tipo=MovimientoCaja.Tipo.ANULACION,
            monto=pago.monto,
            metodo_pago=pago.metodo_pago,
            referencia=f"anulacion:venta:{venta.id}:pago:{pago.id}",
            motivo=motivo,
            usuario=usuario,
        )

    venta.estado = Venta.Estado.ANULADA
    venta.anulada_en = timezone.now()
    venta.anulada_por = usuario
    venta.motivo_anulacion = motivo
    venta.save(update_fields=["estado", "anulada_en", "anulada_por", "motivo_anulacion"])
    return venta
