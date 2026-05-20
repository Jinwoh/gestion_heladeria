from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.caja.models import CajaSesion
from apps.productos.models import Producto


class Venta(models.Model):
    class Estado(models.TextChoices):
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        ANULADA = "ANULADA", "Anulada"

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

    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vuelto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.CONFIRMADA,
    )

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"

    def __str__(self):
        return f"Venta #{self.id} - {self.total}"

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
            partes.append(f"{pago.get_metodo_pago_display()}: {pago.monto}")
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

    class Meta:
        verbose_name = "Pago de venta"
        verbose_name_plural = "Pagos de venta"

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

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"