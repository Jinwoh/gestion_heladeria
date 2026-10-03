from django import forms

from .models import Producto


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["codigo", "nombre", "tipo", "categoria", "unidad_medida", "precio", "stock_minimo", "activo"]
        widgets = {
            "precio": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "stock_minimo": forms.NumberInput(attrs={"min": "0", "step": "0.001"}),
        }

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        precio = cleaned.get("precio")
        unidad = cleaned.get("unidad_medida")
        stock_minimo = cleaned.get("stock_minimo")
        if tipo in {Producto.Tipo.PRODUCTO_REVENTA, Producto.Tipo.PRODUCTO_ELABORADO} and precio is not None and precio <= 0:
            self.add_error("precio", "Los artículos vendibles deben tener un precio mayor a cero.")
        if unidad and stock_minimo is not None and not unidad.permite_decimales and stock_minimo != stock_minimo.to_integral_value():
            self.add_error("stock_minimo", f"La unidad {unidad.abreviatura} no admite decimales.")
        return cleaned
