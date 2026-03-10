from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CajaSesion, MovimientoCaja


def get_caja_abierta(usuario) -> CajaSesion | None:
    """
    Devuelve la caja ABIERTA del usuario (si existe).
    Regla MVP: 1 caja abierta por usuario.
    """
    return (
        CajaSesion.objects
        .filter(usuario=usuario, estado=CajaSesion.Estado.ABIERTA)
        .first()
    )


@transaction.atomic
def abrir_caja(*, usuario, monto_apertura: Decimal, notas: str = "") -> CajaSesion:
    """
    Abre una caja para el usuario si no tiene otra abierta.
    """
    if get_caja_abierta(usuario):
        raise ValidationError("Ya tenés una caja abierta. Cerrala antes de abrir otra.")

    if monto_apertura is None:
        monto_apertura = Decimal("0")

    if monto_apertura < 0:
        raise ValidationError("El monto de apertura no puede ser negativo.")

    caja = CajaSesion.objects.create(
        usuario=usuario,
        estado=CajaSesion.Estado.ABIERTA,
        monto_apertura=monto_apertura,
        notas=notas or "",
    )

    # Auditoría: registrar ingreso inicial como movimiento (opcional, pero recomendado)
    if monto_apertura != 0:
        MovimientoCaja.objects.create(
            caja_sesion=caja,
            tipo=MovimientoCaja.Tipo.INGRESO,
            monto=monto_apertura,
            referencia="apertura",
            motivo="Monto de apertura",
            usuario=usuario,
        )

    return caja


@transaction.atomic
def cerrar_caja(*, usuario, monto_cierre_declarado: Decimal) -> CajaSesion:
    """
    Cierra la caja abierta del usuario.
    """
    caja = get_caja_abierta(usuario)
    if not caja:
        raise ValidationError("No hay caja abierta para cerrar.")

    if monto_cierre_declarado is None:
        raise ValidationError("Debés ingresar el monto de cierre declarado.")

    if monto_cierre_declarado < 0:
        raise ValidationError("El monto de cierre no puede ser negativo.")

    caja.estado = CajaSesion.Estado.CERRADA
    caja.fecha_cierre = timezone.now()
    caja.monto_cierre_declarado = monto_cierre_declarado
    caja.save(update_fields=["estado", "fecha_cierre", "monto_cierre_declarado"])

    return caja


@transaction.atomic
def registrar_movimiento(
    *,
    caja: CajaSesion,
    usuario,
    tipo: str,
    monto: Decimal,
    motivo: str = "",
    referencia: str = "",
) -> MovimientoCaja:
    """
    Registra un movimiento manual (ingreso/egreso/ajuste).
    """
    if caja.estado != CajaSesion.Estado.ABIERTA:
        raise ValidationError("La caja está cerrada. No se pueden registrar movimientos.")

    if monto is None or monto <= 0:
        raise ValidationError("El monto debe ser mayor a 0.")

    return MovimientoCaja.objects.create(
        caja_sesion=caja,
        tipo=tipo,
        monto=monto,
        motivo=motivo,
        referencia=referencia,
        usuario=usuario,
    )