import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q, Sum

from apps.productos.models import Producto, UnidadMedida


class Proveedor(models.Model):
    razon_social = models.CharField(max_length=180)
    ruc = models.CharField(max_length=30, unique=True, blank=True, null=True)
    telefono = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    persona_contacto = models.CharField(max_length=120, blank=True)
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["razon_social"]
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def save(self, *args, **kwargs):
        self.ruc = (self.ruc or "").strip() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.razon_social


class Stock(models.Model):
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name="stock")
    cantidad = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(cantidad__gte=0), name="ck_stock_cantidad_no_negativa")]
        verbose_name = "Stock"
        verbose_name_plural = "Stock"

    def __str__(self) -> str:
        return f"{self.producto.nombre}: {self.cantidad}"


class MovimientoStock(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA_COMPRA = "ENTRADA_COMPRA", "Entrada por compra"
        AJUSTE_POSITIVO = "AJUSTE_POSITIVO", "Ajuste positivo"
        AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO", "Ajuste negativo"
        VENTA = "VENTA", "Venta"
        PRODUCCION_ENTRADA = "PRODUCCION_ENTRADA", "Entrada de producción"
        PRODUCCION_CONSUMO = "PRODUCCION_CONSUMO", "Consumo de producción"
        ANULACION = "ANULACION", "Anulación"
        OTRO = "OTRO", "Otro"

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos_stock")
    tipo_articulo = models.CharField(max_length=24, choices=Producto.Tipo.choices, default=Producto.Tipo.PRODUCTO_REVENTA)
    tipo = models.CharField(max_length=24, choices=Tipo.choices, db_index=True)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    stock_anterior = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    stock_resultante = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    referencia_tipo = models.CharField(max_length=40, blank=True)
    referencia_id = models.PositiveBigIntegerField(blank=True, null=True)
    motivo = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(cantidad=0), name="ck_mov_stock_cantidad_no_cero"),
            models.CheckConstraint(condition=Q(stock_anterior__gte=0), name="ck_mov_stock_anterior_no_negativo"),
            models.CheckConstraint(condition=Q(stock_resultante__gte=0), name="ck_mov_stock_resultante_no_negativo"),
        ]
        indexes = [
            models.Index(fields=["producto", "creado_en"], name="idx_mov_stock_producto_fecha"),
            models.Index(fields=["referencia_tipo", "referencia_id"], name="idx_mov_stock_referencia"),
        ]
        ordering = ["-creado_en", "-pk"]
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.cantidad} - {self.producto.nombre}"


class SecuenciaOrdenCompra(models.Model):
    nombre = models.CharField(max_length=30, primary_key=True)
    ultimo_numero = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = "Secuencia de orden de compra"
        verbose_name_plural = "Secuencias de órdenes de compra"


class OrdenCompra(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        EMITIDA = "EMITIDA", "Emitida"
        PARCIALMENTE_RECIBIDA = "PARCIALMENTE_RECIBIDA", "Parcialmente recibida"
        RECIBIDA = "RECIBIDA", "Recibida"
        CANCELADA = "CANCELADA", "Cancelada"

    numero = models.PositiveBigIntegerField(unique=True, editable=False)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="ordenes_compra")
    tipo = models.CharField(max_length=24, choices=((Producto.Tipo.PRODUCTO_REVENTA, "Producto de reventa"), (Producto.Tipo.INSUMO, "Insumo")), db_index=True)
    estado = models.CharField(max_length=25, choices=Estado.choices, default=Estado.BORRADOR, db_index=True)
    fecha = models.DateField()
    fecha_estimada_entrega = models.DateField(blank=True, null=True)
    observaciones = models.TextField(blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordenes_compra_creadas")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-numero"]
        verbose_name = "Orden de compra"
        verbose_name_plural = "Órdenes de compra"
        permissions = [("emitir_ordencompra", "Puede emitir órdenes de compra"), ("cancelar_ordencompra", "Puede cancelar órdenes de compra"), ("recibir_ordencompra", "Puede recibir órdenes de compra")]
        indexes = [models.Index(fields=["estado", "fecha"], name="idx_oc_estado_fecha"), models.Index(fields=["proveedor", "fecha"], name="idx_oc_proveedor_fecha")]

    def save(self, *args, **kwargs):
        if self.numero is None:
            with transaction.atomic():
                SecuenciaOrdenCompra.objects.get_or_create(nombre="orden_compra")
                secuencia = SecuenciaOrdenCompra.objects.select_for_update().get(nombre="orden_compra")
                SecuenciaOrdenCompra.objects.filter(pk=secuencia.pk).update(ultimo_numero=F("ultimo_numero") + 1)
                secuencia.refresh_from_db(fields=["ultimo_numero"])
                self.numero = secuencia.ultimo_numero
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    @property
    def numero_formateado(self):
        return f"OC-{self.numero:06d}"

    @property
    def total(self):
        if not self.pk:
            return Decimal("0")
        return sum((detalle.subtotal for detalle in self.detalles.all()), Decimal("0"))

    @property
    def puede_editarse(self):
        return self.estado == self.Estado.BORRADOR

    @property
    def puede_recibirse(self):
        return self.estado in {self.Estado.EMITIDA, self.Estado.PARCIALMENTE_RECIBIDA}

    def __str__(self):
        return self.numero_formateado


class DetalleOrdenCompra(models.Model):
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="detalles_compra")
    cantidad_solicitada = models.DecimalField(max_digits=14, decimal_places=3)
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["orden_compra", "producto"], name="uq_oc_producto"),
            models.CheckConstraint(condition=Q(cantidad_solicitada__gt=0), name="ck_detalle_oc_cantidad_positiva"),
            models.CheckConstraint(condition=Q(costo_unitario__gte=0), name="ck_detalle_oc_costo_no_negativo"),
        ]
        verbose_name = "Detalle de orden de compra"
        verbose_name_plural = "Detalles de órdenes de compra"

    def clean(self):
        errors = {}
        if self.producto_id and self.orden_compra_id and self.producto.tipo != self.orden_compra.tipo:
            errors["producto"] = "El artículo no corresponde al tipo de la orden de compra."
        if self.producto_id and self.producto.tipo == Producto.Tipo.PRODUCTO_ELABORADO:
            errors["producto"] = "Los productos elaborados no pueden comprarse mediante una orden."
        if self.producto_id and self.unidad_medida_id and self.producto.unidad_medida_id != self.unidad_medida_id:
            errors["unidad_medida"] = "La unidad debe coincidir con la unidad de inventario del artículo."
        if errors:
            raise ValidationError(errors)

    @property
    def subtotal(self):
        return self.cantidad_solicitada * self.costo_unitario

    @property
    def cantidad_recibida(self):
        return self.detalles_recepcion.aggregate(total=Sum("cantidad_recibida"))["total"] or Decimal("0")

    @property
    def cantidad_pendiente(self):
        return max(self.cantidad_solicitada - self.cantidad_recibida, Decimal("0"))


class RecepcionCompra(models.Model):
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, related_name="recepciones")
    clave_idempotencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    usuario_receptor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recepciones_compra")
    observacion = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha_recepcion", "-pk"]
        verbose_name = "Recepción de compra"
        verbose_name_plural = "Recepciones de compra"

    @property
    def numero_formateado(self):
        return f"RC-{self.pk:06d}" if self.pk else "RC-pendiente"

    def __str__(self):
        return f"{self.numero_formateado} / {self.orden_compra.numero_formateado}"


class DetalleRecepcionCompra(models.Model):
    recepcion = models.ForeignKey(RecepcionCompra, on_delete=models.PROTECT, related_name="detalles")
    detalle_orden = models.ForeignKey(DetalleOrdenCompra, on_delete=models.PROTECT, related_name="detalles_recepcion")
    cantidad_recibida = models.DecimalField(max_digits=14, decimal_places=3)
    movimiento_stock = models.OneToOneField(MovimientoStock, on_delete=models.PROTECT, related_name="detalle_recepcion", blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["recepcion", "detalle_orden"], name="uq_recepcion_detalle_oc"),
            models.CheckConstraint(condition=Q(cantidad_recibida__gt=0), name="ck_recepcion_cantidad_positiva"),
        ]
        verbose_name = "Detalle de recepción de compra"
        verbose_name_plural = "Detalles de recepciones de compra"

    def clean(self):
        if self.recepcion_id and self.detalle_orden_id and self.recepcion.orden_compra_id != self.detalle_orden.orden_compra_id:
            raise ValidationError({"detalle_orden": "El artículo no pertenece a esta orden de compra."})
