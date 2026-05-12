from django import forms

from .models import Caja, MovimientoCaja


class AperturaCajaForm(forms.Form):
    caja = forms.ModelChoiceField(
        queryset=Caja.objects.none(),
        required=True,
        label="Caja",
        empty_label="Seleccioná una caja",
    )
    monto_apertura = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=True,
        label="Monto de apertura",
    )
    notas = forms.CharField(
        max_length=255,
        required=False,
        label="Notas (opcional)",
        widget=forms.TextInput(attrs={"placeholder": "Ej: Cambio inicial"}),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None:
            self.fields["caja"].queryset = Caja.objects.filter(
                activa=True,
                usuarios_habilitados=usuario,
            ).order_by("numero")
        else:
            self.fields["caja"].queryset = Caja.objects.none()


class CierreCajaForm(forms.Form):
    monto_cierre = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=True,
        label="Monto de cierre declarado",
    )
    observacion_diferencia = forms.CharField(
        max_length=255,
        required=False,
        label="Observación de diferencia",
        widget=forms.TextInput(attrs={"placeholder": "Obligatorio si hay diferencia"}),
    )


class MovimientoCajaForm(forms.Form):
    tipo = forms.ChoiceField(
        choices=[
            (MovimientoCaja.Tipo.INGRESO, "Ingreso"),
            (MovimientoCaja.Tipo.EGRESO, "Egreso"),
            (MovimientoCaja.Tipo.AJUSTE, "Ajuste"),
        ],
        required=True,
        label="Tipo de movimiento",
    )
    monto = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        required=True,
        label="Monto",
    )
    motivo = forms.CharField(
        max_length=255,
        required=True,
        label="Motivo",
        widget=forms.TextInput(attrs={"placeholder": "Ej: Compra de insumos, retiro, ajuste"}),
    )
    referencia = forms.CharField(
        max_length=80,
        required=False,
        label="Referencia (opcional)",
        widget=forms.TextInput(attrs={"placeholder": "Ej: factura-001, compra-22"}),
    )