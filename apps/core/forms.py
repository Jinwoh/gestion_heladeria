from django import forms

from .models import ConfiguracionDashboard


class MetaMensualForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionDashboard
        fields = ("meta_mensual",)
        widgets = {
            "meta_mensual": forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "inputmode": "numeric",
                    "aria-label": "Nueva meta mensual",
                }
            )
        }

    def clean_meta_mensual(self):
        meta = self.cleaned_data["meta_mensual"]
        if meta != meta.to_integral_value():
            raise forms.ValidationError("Ingresá la meta en guaraníes, sin decimales.")
        return meta
