from django import forms


class AperturaCajaForm(forms.Form):
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


class CierreCajaForm(forms.Form):
    monto_cierre = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=True,
        label="Monto de cierre declarado",
    )