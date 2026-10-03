from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.productos.models import Producto

from .models import (
    DetalleOrdenCompra,
    DetalleRecepcionCompra,
    MovimientoStock,
    OrdenCompra,
    RecepcionCompra,
    Stock,
)


def _cantidad_decimal(valor, *, permitir_cero=False) -> Decimal:
    try:
        cantidad = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("La cantidad no es válida.")
    if not cantidad.is_finite() or cantidad.as_tuple().exponent < -3:
        raise ValidationError("La cantidad admite hasta tres decimales.")
    if cantidad < 0 or (cantidad == 0 and not permitir_cero):
        raise ValidationError("La cantidad debe ser mayor a cero.")
    return cantidad


def _validar_unidad(producto: Producto, cantidad: Decimal):
    if not producto.unidad_medida.permite_decimales and cantidad != cantidad.to_integral_value():
        raise ValidationError(f"La unidad {producto.unidad_medida.abreviatura} no admite decimales.")


def get_or_create_stock(producto: Producto) -> Stock:
    stock, _ = Stock.objects.get_or_create(producto=producto, defaults={"cantidad": Decimal("0")})
    return stock


def _get_stock_bloqueado(producto: Producto) -> Stock:
    get_or_create_stock(producto)
    return Stock.objects.select_for_update().get(producto=producto)


@transaction.atomic
def registrar_movimiento(*, producto, cantidad, tipo, usuario, motivo="", referencia_tipo="", referencia_id=None):
    cantidad = Decimal(str(cantidad))
    if cantidad == 0:
        raise ValidationError("El movimiento no puede tener cantidad cero.")
    _validar_unidad(producto, abs(cantidad))
    stock = _get_stock_bloqueado(producto)
    anterior = stock.cantidad
    resultante = anterior + cantidad
    if resultante < 0:
        raise ValidationError(f"Stock insuficiente. Disponible: {anterior}")

    stock.cantidad = resultante
    stock.save(update_fields=["cantidad", "actualizado_en"])
    movimiento = MovimientoStock.objects.create(
        producto=producto,
        tipo_articulo=producto.tipo,
        tipo=tipo,
        cantidad=cantidad,
        stock_anterior=anterior,
        stock_resultante=resultante,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        motivo=(motivo or "").strip(),
        usuario=usuario,
    )
    return stock, movimiento


def sumar_stock(*, producto, cantidad, usuario, motivo="", tipo=MovimientoStock.Tipo.OTRO, referencia_tipo="", referencia_id=None):
    cantidad = _cantidad_decimal(cantidad)
    return registrar_movimiento(
        producto=producto,
        cantidad=cantidad,
        tipo=tipo,
        usuario=usuario,
        motivo=motivo,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
    )[0]


def restar_stock(*, producto, cantidad, usuario, motivo="", tipo=MovimientoStock.Tipo.OTRO, referencia_tipo="", referencia_id=None):
    cantidad = _cantidad_decimal(cantidad)
    return registrar_movimiento(
        producto=producto,
        cantidad=-cantidad,
        tipo=tipo,
        usuario=usuario,
        motivo=motivo,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
    )[0]


@transaction.atomic
def ajustar_stock(*, producto, nueva_cantidad, usuario, motivo=""):
    nueva_cantidad = _cantidad_decimal(nueva_cantidad, permitir_cero=True)
    _validar_unidad(producto, nueva_cantidad)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("El motivo del ajuste es obligatorio.")
    stock = _get_stock_bloqueado(producto)
    diferencia = nueva_cantidad - stock.cantidad
    if diferencia == 0:
        raise ValidationError("El stock físico coincide con el stock del sistema; no hay ajuste que registrar.")
    tipo = MovimientoStock.Tipo.AJUSTE_POSITIVO if diferencia > 0 else MovimientoStock.Tipo.AJUSTE_NEGATIVO
    return registrar_movimiento(
        producto=producto,
        cantidad=diferencia,
        tipo=tipo,
        usuario=usuario,
        motivo=motivo,
        referencia_tipo="ajuste_manual",
    )[0]


@transaction.atomic
def emitir_orden(orden, *, usuario):
    orden = OrdenCompra.objects.select_for_update().select_related("proveedor").get(pk=orden.pk)
    if orden.estado != OrdenCompra.Estado.BORRADOR:
        raise ValidationError("Solo se puede emitir una orden en borrador.")
    if not orden.proveedor.activo:
        raise ValidationError("No se puede emitir una orden para un proveedor inactivo.")
    detalles = list(orden.detalles.select_related("producto", "unidad_medida"))
    if not detalles:
        raise ValidationError("La orden debe tener al menos un artículo.")
    for detalle in detalles:
        detalle.full_clean()
    orden.estado = OrdenCompra.Estado.EMITIDA
    orden.save(update_fields=["estado", "actualizado_en"])
    return orden


@transaction.atomic
def cancelar_orden(orden, *, usuario):
    orden = OrdenCompra.objects.select_for_update().get(pk=orden.pk)
    if orden.estado not in {OrdenCompra.Estado.BORRADOR, OrdenCompra.Estado.EMITIDA}:
        raise ValidationError("Esta orden ya no puede cancelarse.")
    if orden.recepciones.exists():
        raise ValidationError("No se puede cancelar una orden que ya tiene recepciones.")
    orden.estado = OrdenCompra.Estado.CANCELADA
    orden.save(update_fields=["estado", "actualizado_en"])
    return orden


@transaction.atomic
def registrar_recepcion(*, orden, cantidades, usuario, clave_idempotencia, observacion=""):
    existente = RecepcionCompra.objects.filter(clave_idempotencia=clave_idempotencia).first()
    if existente:
        if existente.orden_compra_id != orden.pk:
            raise ValidationError("La clave de esta operación ya fue utilizada.")
        return existente, False

    orden = OrdenCompra.objects.select_for_update().get(pk=orden.pk)
    if not orden.puede_recibirse:
        raise ValidationError("La orden no está disponible para recepción.")

    detalles = {
        detalle.pk: detalle
        for detalle in DetalleOrdenCompra.objects.select_for_update()
        .select_related("producto", "producto__unidad_medida")
        .filter(orden_compra=orden)
    }
    recibidos = {
        fila["detalle_orden_id"]: fila["total"] or Decimal("0")
        for fila in DetalleRecepcionCompra.objects.filter(detalle_orden_id__in=detalles)
        .values("detalle_orden_id")
        .annotate(total=Sum("cantidad_recibida"))
    }

    lineas = []
    for detalle_id, valor in cantidades.items():
        try:
            detalle_id = int(detalle_id)
        except (TypeError, ValueError):
            raise ValidationError("Se indicó un detalle de recepción inválido.")
        cantidad = _cantidad_decimal(valor, permitir_cero=True)
        if cantidad == 0:
            continue
        detalle = detalles.get(detalle_id)
        if not detalle:
            raise ValidationError("Uno de los artículos no pertenece a la orden.")
        _validar_unidad(detalle.producto, cantidad)
        pendiente = detalle.cantidad_solicitada - recibidos.get(detalle_id, Decimal("0"))
        if cantidad > pendiente:
            raise ValidationError(f"{detalle.producto.nombre}: no se puede recibir más de {pendiente} {detalle.unidad_medida.abreviatura}.")
        lineas.append((detalle, cantidad))

    if not lineas:
        raise ValidationError("Ingresá al menos una cantidad mayor a cero.")

    try:
        with transaction.atomic():
            recepcion = RecepcionCompra.objects.create(
                orden_compra=orden,
                clave_idempotencia=clave_idempotencia,
                usuario_receptor=usuario,
                observacion=(observacion or "").strip(),
            )
    except IntegrityError:
        recepcion = RecepcionCompra.objects.get(clave_idempotencia=clave_idempotencia)
        if recepcion.orden_compra_id != orden.pk:
            raise ValidationError("La clave de esta operación ya fue utilizada.")
        return recepcion, False

    for detalle, cantidad in lineas:
        detalle_recepcion = DetalleRecepcionCompra.objects.create(
            recepcion=recepcion,
            detalle_orden=detalle,
            cantidad_recibida=cantidad,
        )
        _, movimiento = registrar_movimiento(
            producto=detalle.producto,
            cantidad=cantidad,
            tipo=MovimientoStock.Tipo.ENTRADA_COMPRA,
            usuario=usuario,
            motivo=f"Recepción {recepcion.numero_formateado} / {orden.numero_formateado}",
            referencia_tipo="recepcion_compra",
            referencia_id=recepcion.pk,
        )
        detalle_recepcion.movimiento_stock = movimiento
        detalle_recepcion.save(update_fields=["movimiento_stock"])
        detalle.producto.ultimo_costo = detalle.costo_unitario
        detalle.producto.save(update_fields=["ultimo_costo", "actualizado_en"])

    queda_pendiente = False
    for detalle in detalles.values():
        total_recibido = detalle.detalles_recepcion.aggregate(total=Sum("cantidad_recibida"))["total"] or Decimal("0")
        if total_recibido < detalle.cantidad_solicitada:
            queda_pendiente = True
            break
    orden.estado = OrdenCompra.Estado.PARCIALMENTE_RECIBIDA if queda_pendiente else OrdenCompra.Estado.RECIBIDA
    orden.save(update_fields=["estado", "actualizado_en"])
    return recepcion, True
