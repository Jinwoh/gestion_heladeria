from django.db import migrations


def completar_stock(apps, schema_editor):
    Producto = apps.get_model("productos", "Producto")
    Stock = apps.get_model("inventario", "Stock")
    existentes = set(Stock.objects.values_list("producto_id", flat=True))
    Stock.objects.bulk_create(
        Stock(producto_id=producto_id, cantidad=0)
        for producto_id in Producto.objects.exclude(pk__in=existentes).values_list("pk", flat=True)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0002_movimientostock_ck_mov_stock_cantidad_valida_and_more"),
        ("productos", "0003_remove_producto_ck_producto_precio_no_negativo_and_more"),
    ]

    operations = [migrations.RunPython(completar_stock, migrations.RunPython.noop)]
