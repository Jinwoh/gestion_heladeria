from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from apps.productos.models import Producto

from .models import DetalleOrdenCompra, OrdenCompra, Proveedor


class AjusteStockForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).select_related("categoria", "unidad_medida"),
        label="Artículo",
    )
    cantidad = forms.DecimalField(
        min_value=0,
        max_digits=14,
        decimal_places=3,
        label="Stock físico contado",
        widget=forms.NumberInput(attrs={"step": "0.001", "min": "0"}),
    )
    motivo = forms.CharField(max_length=255, label="Motivo del ajuste", widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        producto = cleaned.get("producto")
        cantidad = cleaned.get("cantidad")
        if producto and cantidad is not None and not producto.unidad_medida.permite_decimales and cantidad != cantidad.to_integral_value():
            self.add_error("cantidad", f"La unidad {producto.unidad_medida.abreviatura} no admite decimales.")
        return cleaned


# Alias de compatibilidad con imports anteriores.
MovimientoStockForm = AjusteStockForm


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["razon_social", "ruc", "telefono", "email", "direccion", "persona_contacto", "observaciones", "activo"]
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 3})}


class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenCompra
        fields = ["proveedor", "tipo", "fecha", "fecha_estimada_entrega", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "fecha_estimada_entrega": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        proveedores = Proveedor.objects.filter(activo=True)
        if self.instance.pk:
            proveedores = Proveedor.objects.filter(models.Q(activo=True) | models.Q(pk=self.instance.proveedor_id))
        self.fields["proveedor"].queryset = proveedores.order_by("razon_social")
        if not self.is_bound and not self.instance.pk:
            self.initial["fecha"] = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and "tipo" in self.changed_data and self.instance.detalles.exists():
            self.add_error("tipo", "No se puede cambiar el tipo de una orden que ya tiene artículos; quitá primero sus detalles.")
        return cleaned


class DetalleOrdenCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleOrdenCompra
        fields = ["producto", "cantidad_solicitada", "unidad_medida", "costo_unitario"]
        widgets = {
            "cantidad_solicitada": forms.NumberInput(attrs={"min": "0.001", "step": "0.001"}),
            "costo_unitario": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
        }

    def __init__(self, *args, tipo_orden=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo_orden = tipo_orden
        qs = Producto.objects.filter(activo=True, tipo__in=[Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.INSUMO]).select_related("unidad_medida", "categoria")
        if tipo_orden in {Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.INSUMO}:
            qs = qs.filter(tipo=tipo_orden)
        self.fields["producto"].queryset = qs.order_by("nombre")

    def clean(self):
        cleaned = super().clean()
        producto = cleaned.get("producto")
        unidad = cleaned.get("unidad_medida")
        cantidad = cleaned.get("cantidad_solicitada")
        if producto:
            if self.tipo_orden and producto.tipo != self.tipo_orden:
                self.add_error("producto", "El artículo no corresponde al tipo de la orden.")
            if producto.tipo == Producto.Tipo.PRODUCTO_ELABORADO:
                self.add_error("producto", "Un producto elaborado no puede incluirse en compras.")
            if unidad and unidad.pk != producto.unidad_medida_id:
                self.add_error("unidad_medida", "Seleccioná la unidad de inventario del artículo.")
            if cantidad is not None and not producto.unidad_medida.permite_decimales and cantidad != cantidad.to_integral_value():
                self.add_error("cantidad_solicitada", f"La unidad {producto.unidad_medida.abreviatura} no admite decimales.")
        return cleaned


class BaseDetalleOrdenFormSet(BaseInlineFormSet):
    def __init__(self, *args, tipo_orden=None, **kwargs):
        self.tipo_orden = tipo_orden
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.tipo_orden = tipo_orden
            if tipo_orden in {Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.INSUMO}:
                form.fields["producto"].queryset = form.fields["producto"].queryset.filter(tipo=tipo_orden)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        productos = set()
        lineas = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            producto = form.cleaned_data.get("producto")
            if not producto:
                continue
            lineas += 1
            if producto.pk in productos:
                raise ValidationError("No se puede repetir un artículo en la misma orden.")
            productos.add(producto.pk)
            if self.tipo_orden and producto.tipo != self.tipo_orden:
                raise ValidationError("Todos los artículos deben coincidir con el tipo de la orden.")
        if lineas == 0:
            raise ValidationError("Agregá al menos un artículo a la orden.")


DetalleOrdenFormSet = inlineformset_factory(
    OrdenCompra,
    DetalleOrdenCompra,
    form=DetalleOrdenCompraForm,
    formset=BaseDetalleOrdenFormSet,
    extra=1,
    can_delete=True,
)
