from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def gs(value):
    try:
        n = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value

    s = f"{n:,.0f}"
    s = s.replace(",", ".")
    return f"Gs. {s}"