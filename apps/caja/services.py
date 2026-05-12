from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Caja, CajaSesion, MovimientoCaja


def get_caja_abierta(usuario) -> CajaSesion | None:
    return (
        CajaSesion.objects
        .select_related("caja")
        .filter(usuario=usuario, estado=CajaSesion.Estado.ABIERTA)
        .first()
    )


def get_sesion_abierta_por_caja(caja: Caja) -> CajaSesion | None:
    return (
        CajaSesion.objects
        .select_related("usuario", "caja")
        .filter(caja=caja, estado=CajaSesion.Estado.ABIERTA)
        .first()
    )


@transaction.atomic
def abrir_caja(*, usuario, caja: Caja, monto_apertura: Decimal, notas: str = "") -> CajaSesion:
    if get_caja_abierta(usuario):
        raise ValidationError("Ya tenés una caja abierta. Cerrala antes de abrir otra.")

    if not caja.activa:
        raise ValidationError("La caja seleccionada está inactiva.")

    if not caja.usuarios_habilitados.filter(pk=usuario.pk).exists():
        raise ValidationError("No tenés permiso para abrir esa caja.")

    if get_sesion_abierta_por_caja(caja):
        raise ValidationError("La caja seleccionada ya está abierta por otro usuario.")

    if monto_apertura is None:
        monto_apertura = Decimal("0")

    if monto_apertura < 0:
        raise ValidationError("El monto de apertura no puede ser negativo.")

    sesion = CajaSesion.objects.create(
        caja=caja,
        usuario=usuario,
        estado=CajaSesion.Estado.ABIERTA,
        monto_apertura=monto_apertura,
        notas=notas or "",
    )

    if monto_apertura != 0:
        MovimientoCaja.objects.create(
            caja_sesion=sesion,
            tipo=MovimientoCaja.Tipo.INGRESO,
            monto=monto_apertura,
            referencia="apertura",
            motivo="Monto de apertura",
            usuario=usuario,
        )

    return sesion


@transaction.atomic
def cerrar_caja(*, usuario, monto_cierre_declarado: Decimal, observacion_diferencia: str = "") -> CajaSesion:
    caja = get_caja_abierta(usuario)
    if not caja:
        raise ValidationError("No hay caja abierta para cerrar.")

    if monto_cierre_declarado is None:
        raise ValidationError("Debés ingresar el monto de cierre declarado.")

    if monto_cierre_declarado < 0:
        raise ValidationError("El monto de cierre no puede ser negativo.")

    ingresos = sum(
        m.monto for m in caja.movimientos.filter(tipo=MovimientoCaja.Tipo.INGRESO)
    )
    egresos = sum(
        m.monto for m in caja.movimientos.filter(tipo=MovimientoCaja.Tipo.EGRESO)
    )
    ventas_efectivo = sum(
        m.monto
        for m in caja.movimientos.filter(
            tipo=MovimientoCaja.Tipo.VENTA,
            metodo_pago=MovimientoCaja.MetodoPago.EFECTIVO,
        )
    )

    esperado = ingresos + ventas_efectivo - egresos
    diferencia = monto_cierre_declarado - esperado

    if diferencia != 0 and not observacion_diferencia.strip():
        raise ValidationError("Debés ingresar una observación cuando hay diferencia de caja.")

    caja.estado = CajaSesion.Estado.CERRADA
    caja.fecha_cierre = timezone.now()
    caja.monto_cierre_declarado = monto_cierre_declarado
    caja.observacion_diferencia = observacion_diferencia.strip()
    caja.save(
        update_fields=[
            "estado",
            "fecha_cierre",
            "monto_cierre_declarado",
            "observacion_diferencia",
        ]
    )

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
    metodo_pago: str | None = None,
) -> MovimientoCaja:
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
        metodo_pago=metodo_pago,
        usuario=usuario,
    )