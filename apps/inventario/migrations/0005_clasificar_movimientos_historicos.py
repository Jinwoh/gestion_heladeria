import re

from django.db import migrations


def clasificar_movimientos(apps, schema_editor):
    Movimiento = apps.get_model("inventario", "MovimientoStock")
    for movimiento in Movimiento.objects.filter(referencia_tipo="historico"):
        motivo = (movimiento.motivo or "").strip()
        venta = re.match(r"^Venta\s+#?(\d+)$", motivo, flags=re.IGNORECASE)
        anulacion = re.match(r"^Anulaci[oó]n de venta\s+#?(\d+)$", motivo, flags=re.IGNORECASE)
        if venta:
            Movimiento.objects.filter(pk=movimiento.pk).update(
                tipo="VENTA",
                referencia_tipo="venta",
                referencia_id=int(venta.group(1)),
            )
        elif anulacion:
            Movimiento.objects.filter(pk=movimiento.pk).update(
                tipo="ANULACION",
                referencia_tipo="venta",
                referencia_id=int(anulacion.group(1)),
            )


class Migration(migrations.Migration):
    dependencies = [("inventario", "0004_detalleordencompra_detallerecepcioncompra_and_more")]
    operations = [migrations.RunPython(clasificar_movimientos, migrations.RunPython.noop)]
