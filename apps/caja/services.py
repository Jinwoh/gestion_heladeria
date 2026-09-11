from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
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
    caja = Caja.objects.select_for_update().get(pk=caja.pk)
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

    try:
        sesion = CajaSesion.objects.create(
            caja=caja,
            usuario=usuario,
            estado=CajaSesion.Estado.ABIERTA,
            monto_apertura=monto_apertura,
            notas=notas or "",
        )
    except IntegrityError as exc:
        raise ValidationError("El usuario o la caja ya tiene una sesión abierta.") from exc

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
    caja = (
        CajaSesion.objects.select_for_update()
        .select_related("caja")
        .filter(usuario=usuario, estado=CajaSesion.Estado.ABIERTA)
        .first()
    )
    if not caja:
        raise ValidationError("No hay caja abierta para cerrar.")

    if monto_cierre_declarado is None:
        raise ValidationError("Debés ingresar el monto de cierre declarado.")

    if monto_cierre_declarado < 0:
        raise ValidationError("El monto de cierre no puede ser negativo.")

    esperado = resumen_caja(caja)["esperado"]
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
    caja = CajaSesion.objects.select_for_update().get(pk=caja.pk)
    if caja.estado != CajaSesion.Estado.ABIERTA:
        raise ValidationError("La caja está cerrada. No se pueden registrar movimientos.")
    if caja.usuario_id != usuario.pk:
        raise ValidationError("No podés registrar movimientos en la caja de otro usuario.")

    if monto is None or monto <= 0:
        raise ValidationError("El monto debe ser mayor a 0.")

    tipos_manuales = {
        MovimientoCaja.Tipo.INGRESO,
        MovimientoCaja.Tipo.EGRESO,
        MovimientoCaja.Tipo.AJUSTE_INGRESO,
        MovimientoCaja.Tipo.AJUSTE_EGRESO,
    }
    if tipo not in tipos_manuales:
        raise ValidationError("El tipo de movimiento manual no es válido.")

    return MovimientoCaja.objects.create(
        caja_sesion=caja,
        tipo=tipo,
        monto=monto,
        motivo=motivo,
        referencia=referencia,
        metodo_pago=metodo_pago,
        usuario=usuario,
    )


def resumen_caja(caja: CajaSesion) -> dict:
    """Calcula una única definición contable reutilizable para arqueo y cierre."""
    datos = caja.movimientos.aggregate(
        ingresos=Sum(
            "monto",
            filter=Q(tipo__in=[MovimientoCaja.Tipo.INGRESO, MovimientoCaja.Tipo.AJUSTE_INGRESO]),
        ),
        egresos=Sum(
            "monto",
            filter=Q(tipo__in=[MovimientoCaja.Tipo.EGRESO, MovimientoCaja.Tipo.AJUSTE_EGRESO]),
        ),
        ventas_efectivo=Sum(
            "monto",
            filter=Q(tipo=MovimientoCaja.Tipo.VENTA, metodo_pago=MovimientoCaja.MetodoPago.EFECTIVO),
        ),
        ventas_tarjeta=Sum(
            "monto",
            filter=Q(tipo=MovimientoCaja.Tipo.VENTA, metodo_pago=MovimientoCaja.MetodoPago.TARJETA),
        ),
        ventas_qr=Sum(
            "monto",
            filter=Q(tipo=MovimientoCaja.Tipo.VENTA, metodo_pago=MovimientoCaja.MetodoPago.QR),
        ),
        anulaciones_efectivo=Sum(
            "monto",
            filter=Q(tipo=MovimientoCaja.Tipo.ANULACION, metodo_pago=MovimientoCaja.MetodoPago.EFECTIVO),
        ),
        anulaciones_tarjeta=Sum(
            "monto",
            filter=Q(tipo=MovimientoCaja.Tipo.ANULACION, metodo_pago=MovimientoCaja.MetodoPago.TARJETA),
        ),
        anulaciones_qr=Sum(
            "monto",
            filter=Q(tipo=MovimientoCaja.Tipo.ANULACION, metodo_pago=MovimientoCaja.MetodoPago.QR),
        ),
    )
    valores = {clave: valor or Decimal("0") for clave, valor in datos.items()}
    valores["total_ingresos"] = valores["ingresos"]
    valores["total_egresos"] = valores["egresos"]
    valores["total_ventas"] = (
        valores["ventas_efectivo"] + valores["ventas_tarjeta"] + valores["ventas_qr"]
    )
    valores["total_anulaciones"] = (
        valores["anulaciones_efectivo"]
        + valores["anulaciones_tarjeta"]
        + valores["anulaciones_qr"]
    )
    valores["esperado"] = (
        valores["ingresos"]
        + valores["ventas_efectivo"]
        - valores["egresos"]
        - valores["anulaciones_efectivo"]
    )
    return valores
