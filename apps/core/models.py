from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class ConfiguracionDashboard(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    meta_mensual = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
    )
    actualizada_en = models.DateTimeField(auto_now=True)
    actualizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="configuraciones_dashboard_actualizadas",
    )

    class Meta:
        verbose_name = "Configuración del dashboard"
        verbose_name_plural = "Configuración del dashboard"

    def __str__(self):
        return f"Meta mensual: {self.meta_mensual}"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
