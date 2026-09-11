from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.productos.models import Producto

from .models import Stock


@receiver(post_save, sender=Producto)
def crear_stock_de_producto(sender, instance, created, **kwargs):
    if created:
        Stock.objects.get_or_create(producto=instance)
