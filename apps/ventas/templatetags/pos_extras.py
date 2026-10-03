from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

@register.filter
def get_item(d: dict, key):
    try:
        return d.get(key)
    except Exception:
        return None


@register.filter
def gs(value):
    try:
        numero = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value

    return f"{numero:,.0f}".replace(",", ".") + "Gs"


@register.filter
def cantidad(value):
    """Cantidad sin ceros decimales innecesarios, apta también para atributos HTML."""
    try:
        numero = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    return format(numero, "f").rstrip("0").rstrip(".") or "0"
