from django.conf import settings
from django.db import models
from django.db.models import Q


class Caja(models.Model):
    numero = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100, blank=True)
    activa = models.BooleanField(default=True)
    usuarios_habilitados = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="cajas_habilitadas",
        blank=True,
    )

    class Meta:
        ordering = ["numero"]
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"

    def __str__(self) -> str:
        if self.nombre:
            return f"Caja {self.numero} - {self.nombre}"
        return f"Caja {self.numero}"


class CajaSesion(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = "ABIERTA", "Abierta"
        CERRADA = "CERRADA", "Cerrada"

    caja = models.ForeignKey(
        Caja,
        on_delete=models.PROTECT,
        related_name="sesiones",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cajas",
    )
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ABIERTA,
    )

    fecha_apertura = models.DateTimeField(auto_now_add=True)
    monto_apertura = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    fecha_cierre = models.DateTimeField(blank=True, null=True)
    monto_cierre_declarado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    notas = models.CharField(max_length=255, blank=True)
    observacion_diferencia = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-fecha_apertura"]
        verbose_name = "Caja (Sesión)"
        verbose_name_plural = "Cajas (Sesiones)"
        constraints = [
            models.UniqueConstraint(
                fields=["caja"],
                condition=Q(estado="ABIERTA"),
                name="uq_caja_una_sesion_abierta",
            ),
            models.UniqueConstraint(
                fields=["usuario"],
                condition=Q(estado="ABIERTA"),
                name="uq_usuario_una_caja_abierta",
            ),
            models.CheckConstraint(
                condition=Q(monto_apertura__gte=0),
                name="ck_caja_monto_apertura_no_negativo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(monto_cierre_declarado__isnull=True)
                    | Q(monto_cierre_declarado__gte=0)
                ),
                name="ck_caja_monto_cierre_no_negativo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        estado="ABIERTA",
                        fecha_cierre__isnull=True,
                        monto_cierre_declarado__isnull=True,
                    )
                    | Q(
                        estado="CERRADA",
                        fecha_cierre__isnull=False,
                        monto_cierre_declarado__isnull=False,
                    )
                ),
                name="ck_caja_estado_cierre_consistente",
            ),
        ]
        indexes = [
            models.Index(fields=["estado", "fecha_apertura"], name="idx_caja_estado_fecha"),
        ]

    def __str__(self) -> str:
        return f"{self.caja} - {self.usuario} - {self.estado}"


class MovimientoCaja(models.Model):
    class Tipo(models.TextChoices):
        VENTA = "VENTA", "Venta"
        ANULACION = "ANULACION", "Anulación de venta"
        INGRESO = "INGRESO", "Ingreso"
        EGRESO = "EGRESO", "Egreso"
        AJUSTE_INGRESO = "AJUSTE_IN", "Ajuste positivo"
        AJUSTE_EGRESO = "AJUSTE_OUT", "Ajuste negativo"

    class MetodoPago(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TARJETA = "tarjeta", "Tarjeta"
        QR = "qr", "QR"

    metodo_pago = models.CharField(
        max_length=12,
        choices=MetodoPago.choices,
        blank=True,
        null=True,
    )

    caja_sesion = models.ForeignKey(
        CajaSesion,
        on_delete=models.PROTECT,
        related_name="movimientos",
    )


    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)

    referencia = models.CharField(max_length=80, blank=True)
    motivo = models.CharField(max_length=255, blank=True)

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        constraints = [
            models.CheckConstraint(
                condition=Q(monto__gt=0),
                name="ck_mov_caja_monto_positivo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(tipo__in=["VENTA", "ANULACION"], metodo_pago__isnull=False)
                    | Q(
                        tipo__in=["INGRESO", "EGRESO", "AJUSTE_IN", "AJUSTE_OUT"],
                        metodo_pago__isnull=True,
                    )
                ),
                name="ck_mov_caja_metodo_consistente",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tipo} {self.monto} ({self.caja_sesion.caja})"
