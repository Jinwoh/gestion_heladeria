from django.db import models


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


class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    nombre = models.CharField(max_length=180)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.BooleanField(default=True)
    codigo = models.CharField(max_length=50, blank=True, null=True, unique=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["categoria", "nombre"], name="uq_ventas_producto_categoria_nombre"),
        ]
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.categoria})"