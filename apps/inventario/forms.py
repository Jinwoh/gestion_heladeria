from django import forms

from apps.productos.models import Producto


class MovimientoStockForm(forms.Form):
    ACCIONES = (("entrada", "Registrar entrada"), ("ajuste", "Ajustar existencia"))

    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).select_related("categoria"),
        label="Producto",
    )
    accion = forms.ChoiceField(choices=ACCIONES, label="Operación")
    cantidad = forms.IntegerField(min_value=0, label="Cantidad")
    motivo = forms.CharField(max_length=255, label="Motivo")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("accion") == "entrada" and cleaned.get("cantidad") == 0:
            self.add_error("cantidad", "La entrada debe ser mayor a cero.")
        return cleaned
