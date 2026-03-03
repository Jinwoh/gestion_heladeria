from django.db import transaction
from django.core.exceptions import ValidationError
from apps.productos.models import Producto
from .models import Stock, MovimientoStock


def get_or_create_stock(producto: Producto) -> Stock:
    stock, _ = Stock.objects.get_or_create(producto=producto, defaults={"cantidad": 0})
    return stock


@transaction.atomic
def sumar_stock(*, producto: Producto, cantidad: int, usuario, motivo: str = "") -> Stock:
    if cantidad <= 0:
        raise ValidationError("La cantidad debe ser mayor a 0.")

    stock = get_or_create_stock(producto)
    stock.cantidad += cantidad
    stock.save(update_fields=["cantidad", "actualizado_en"])

    MovimientoStock.objects.create(
        producto=producto,
        tipo=MovimientoStock.Tipo.ENTRADA,
        cantidad=cantidad,
        motivo=motivo,
        usuario=usuario,
    )
    return stock


@transaction.atomic
def restar_stock(*, producto: Producto, cantidad: int, usuario, motivo: str = "") -> Stock:
    if cantidad <= 0:
        raise ValidationError("La cantidad debe ser mayor a 0.")

    stock = get_or_create_stock(producto)
    if stock.cantidad < cantidad:
        raise ValidationError(f"Stock insuficiente. Disponible: {stock.cantidad}")

    stock.cantidad -= cantidad
    stock.save(update_fields=["cantidad", "actualizado_en"])

    MovimientoStock.objects.create(
        producto=producto,
        tipo=MovimientoStock.Tipo.SALIDA,
        cantidad=cantidad,
        motivo=motivo,
        usuario=usuario,
    )
    return stock


@transaction.atomic
def ajustar_stock(*, producto: Producto, nueva_cantidad: int, usuario, motivo: str = "") -> Stock:
    if nueva_cantidad < 0:
        raise ValidationError("La cantidad no puede ser negativa.")

    stock = get_or_create_stock(producto)
    diferencia = nueva_cantidad - stock.cantidad

    stock.cantidad = nueva_cantidad
    stock.save(update_fields=["cantidad", "actualizado_en"])

    MovimientoStock.objects.create(
        producto=producto,
        tipo=MovimientoStock.Tipo.AJUSTE,
        cantidad=diferencia,
        motivo=motivo or "Ajuste de stock",
        usuario=usuario,
    )
    return stock