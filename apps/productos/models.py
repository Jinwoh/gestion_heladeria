from django.db import models
from django.db.models import Q


class Categoria(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def __str__(self) -> str:
        return self.nombre


class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    abreviatura = models.CharField(max_length=12, unique=True)
    permite_decimales = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Unidad de medida"
        verbose_name_plural = "Unidades de medida"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.abreviatura})"


class Producto(models.Model):
    class Tipo(models.TextChoices):
        PRODUCTO_REVENTA = "PRODUCTO_REVENTA", "Producto de reventa"
        INSUMO = "INSUMO", "Insumo"
        PRODUCTO_ELABORADO = "PRODUCTO_ELABORADO", "Producto elaborado"

    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    nombre = models.CharField(max_length=180)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    tipo = models.CharField(
        max_length=24,
        choices=Tipo.choices,
        default=Tipo.PRODUCTO_REVENTA,
        db_index=True,
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    stock_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    ultimo_costo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
    )
    activo = models.BooleanField(default=True)
    codigo = models.CharField(max_length=50, blank=True, null=True, unique=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["categoria", "nombre"],
                name="uq_productos_producto_categoria_nombre",
            ),
            models.CheckConstraint(
                condition=(
                    Q(tipo="INSUMO", precio__gte=0)
                    | Q(tipo__in=["PRODUCTO_REVENTA", "PRODUCTO_ELABORADO"], precio__gt=0)
                ),
                name="ck_producto_precio_segun_tipo",
            ),
            models.CheckConstraint(condition=Q(stock_minimo__gte=0), name="ck_producto_stock_minimo_no_negativo"),
            models.CheckConstraint(
                condition=Q(ultimo_costo__isnull=True) | Q(ultimo_costo__gte=0),
                name="ck_producto_ultimo_costo_no_negativo",
            ),
        ]
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.categoria})"

    def save(self, *args, **kwargs):
        if not self.unidad_medida_id:
            unidad, _ = UnidadMedida.objects.get_or_create(
                abreviatura="un",
                defaults={"nombre": "Unidad", "permite_decimales": False},
            )
            self.unidad_medida = unidad
        super().save(*args, **kwargs)

    @property
    def es_comprable(self) -> bool:
        return self.tipo in {self.Tipo.PRODUCTO_REVENTA, self.Tipo.INSUMO}

    @property
    def es_vendible(self) -> bool:
        return self.tipo in {self.Tipo.PRODUCTO_REVENTA, self.Tipo.PRODUCTO_ELABORADO}
