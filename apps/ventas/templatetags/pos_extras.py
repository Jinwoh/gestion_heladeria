from django import template

register = template.Library()

@register.filter
def get_item(d: dict, key):
    try:
        return d.get(key)
    except Exception:
        return None