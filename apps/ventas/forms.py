from django import forms


class PosVentaForm(forms.Form):
    """
    Recibe arrays: producto_id[] y cantidad[]
    """
    producto_id = forms.IntegerField(required=False)
    cantidad = forms.IntegerField(required=False, min_value=0)