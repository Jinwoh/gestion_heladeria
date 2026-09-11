from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.productos.models import Producto


class Stock(models.Model):
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name="stock")
    cantidad = models.IntegerField(default=0)

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidad__gte=0),
                name="ck_stock_cantidad_no_negativa",
            ),
        ]
        verbose_name = "Stock"
        verbose_name_plural = "Stock"

    def __str__(self) -> str:
        return f"{self.producto.nombre}: {self.cantidad}"


class MovimientoStock(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SALIDA = "SALIDA", "Salida"
        AJUSTE = "AJUSTE", "Ajuste"

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos_stock")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    cantidad = models.IntegerField()
    motivo = models.CharField(max_length=255, blank=True)

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(tipo="AJUSTE")
                    | Q(tipo__in=["ENTRADA", "SALIDA"], cantidad__gt=0)
                ),
                name="ck_mov_stock_cantidad_valida",
            ),
        ]
        ordering = ["-creado_en"]
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"

    def __str__(self) -> str:
        return f"{self.tipo} {self.cantidad} - {self.producto.nombre}"
