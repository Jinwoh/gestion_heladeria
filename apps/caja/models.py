from django.conf import settings
from django.db import models


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

    def __str__(self) -> str:
        return f"{self.caja} - {self.usuario} - {self.estado}"


class MovimientoCaja(models.Model):
    class Tipo(models.TextChoices):
        VENTA = "VENTA", "Venta"
        INGRESO = "INGRESO", "Ingreso"
        EGRESO = "EGRESO", "Egreso"
        AJUSTE = "AJUSTE", "Ajuste"

    class MetodoPago(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TARJETA = "tarjeta", "Tarjeta"
        QR = "qr", "QR"

    caja_sesion = models.ForeignKey(
        CajaSesion,
        on_delete=models.PROTECT,
        related_name="movimientos",
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)

    metodo_pago = models.CharField(
        max_length=12,
        choices=MetodoPago.choices,
        blank=True,
        null=True,
    )

    referencia = models.CharField(max_length=80, blank=True)
    motivo = models.CharField(max_length=255, blank=True)

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"

    def __str__(self) -> str:
        return f"{self.tipo} {self.monto} ({self.caja_sesion.caja})"