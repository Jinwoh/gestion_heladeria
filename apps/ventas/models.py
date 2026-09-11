from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q

from apps.caja.models import CajaSesion
from apps.productos.models import Producto
from apps.clientes.models import Cliente


class Venta(models.Model):
    class Estado(models.TextChoices):
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        ANULADA = "ANULADA", "Anulada"

    numero_ticket = models.PositiveIntegerField(
        unique=True,
    )

    caja_sesion = models.ForeignKey(
        CajaSesion,
        on_delete=models.PROTECT,
        related_name="ventas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ventas",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="ventas",
        null=True,
        blank=True,
    )

    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vuelto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    anulada_en = models.DateTimeField(blank=True, null=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ventas_anuladas",
        blank=True,
        null=True,
    )
    motivo_anulacion = models.CharField(max_length=255, blank=True)
    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.CONFIRMADA,
    )

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        permissions = [
            ("view_global_reports", "Puede ver reportes globales de ventas"),
            ("cancel_venta", "Puede anular ventas"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0), name="ck_venta_total_no_negativo"),
            models.CheckConstraint(condition=Q(vuelto__gte=0), name="ck_venta_vuelto_no_negativo"),
            models.CheckConstraint(
                condition=(
                    Q(
                        estado="CONFIRMADA",
                        anulada_en__isnull=True,
                        anulada_por__isnull=True,
                        motivo_anulacion="",
                    )
                    | (
                        Q(estado="ANULADA", anulada_en__isnull=False, anulada_por__isnull=False)
                        & ~Q(motivo_anulacion="")
                    )
                ),
                name="ck_venta_anulacion_consistente",
            ),
        ]
        indexes = [
            models.Index(fields=["estado", "fecha"], name="idx_venta_estado_fecha"),
            models.Index(fields=["usuario", "fecha"], name="idx_venta_usuario_fecha"),
        ]

    def save(self, *args, **kwargs):
        if self.numero_ticket is None:
            with transaction.atomic():
                SecuenciaTicket.objects.get_or_create(nombre="venta")
                secuencia = SecuenciaTicket.objects.select_for_update().get(nombre="venta")
                SecuenciaTicket.objects.filter(pk=secuencia.pk).update(
                    ultimo_numero=F("ultimo_numero") + 1
                )
                secuencia.refresh_from_db(fields=["ultimo_numero"])
                self.numero_ticket = secuencia.ultimo_numero
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ticket #{self.numero_ticket} - {self.total}"

    def monto_por_metodo(self, metodo_pago: str) -> Decimal:
        return sum(
            (p.monto for p in self.pagos.filter(metodo_pago=metodo_pago)),
            Decimal("0"),
        )

    @property
    def total_efectivo(self) -> Decimal:
        return self.monto_por_metodo(VentaPago.MetodoPago.EFECTIVO)

    @property
    def total_tarjeta(self) -> Decimal:
        return self.monto_por_metodo(VentaPago.MetodoPago.TARJETA)

    @property
    def total_qr(self) -> Decimal:
        return self.monto_por_metodo(VentaPago.MetodoPago.QR)

    @property
    def pagos_resumen(self) -> str:
        partes = []
        for pago in self.pagos.all():
            texto = f"{pago.get_metodo_pago_display()}: {pago.monto}"
            if pago.monto_recibido != pago.monto:
                texto += f" (recibido: {pago.monto_recibido})"
            partes.append(texto)
        if self.vuelto > 0:
            partes.append(f"Vuelto: {self.vuelto}")
        return " | ".join(partes) if partes else "-"


class VentaPago(models.Model):
    class MetodoPago(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TARJETA = "tarjeta", "Tarjeta"
        QR = "qr", "QR"

    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name="pagos",
    )
    metodo_pago = models.CharField(
        max_length=12,
        choices=MetodoPago.choices,
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    monto_recibido = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Pago de venta"
        verbose_name_plural = "Pagos de venta"
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="ck_pago_monto_positivo"),
            models.CheckConstraint(
                condition=Q(monto_recibido__gte=F("monto")),
                name="ck_pago_recibido_mayor_aplicado",
            ),
        ]

    def __str__(self):
        return f"Venta #{self.venta_id} - {self.get_metodo_pago_display()} - {self.monto}"


class VentaDetalle(models.Model):
    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
    )

    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_detalle_cantidad_positiva"),
            models.CheckConstraint(condition=Q(precio_unitario__gte=0), name="ck_detalle_precio_no_negativo"),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="ck_detalle_subtotal_no_negativo"),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"


class SecuenciaTicket(models.Model):
    nombre = models.CharField(max_length=30, primary_key=True)
    ultimo_numero = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = "Secuencia de ticket"
        verbose_name_plural = "Secuencias de tickets"

    def __str__(self):
        return f"{self.nombre}: {self.ultimo_numero}"
