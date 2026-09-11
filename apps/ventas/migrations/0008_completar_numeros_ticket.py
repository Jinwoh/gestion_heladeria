from django.db import migrations, models
from django.db.models import Max


def completar_numeros(apps, schema_editor):
    Venta = apps.get_model("ventas", "Venta")
    SecuenciaTicket = apps.get_model("ventas", "SecuenciaTicket")

    secuencia, _ = SecuenciaTicket.objects.get_or_create(nombre="venta")
    maximo = Venta.objects.exclude(numero_ticket__isnull=True).aggregate(
        numero=Max("numero_ticket")
    )["numero"] or 0
    actual = max(secuencia.ultimo_numero, maximo)
    for venta in Venta.objects.filter(numero_ticket__isnull=True).order_by("fecha", "pk"):
        actual += 1
        Venta.objects.filter(pk=venta.pk).update(numero_ticket=actual)
    SecuenciaTicket.objects.filter(pk=secuencia.pk).update(ultimo_numero=actual)


class Migration(migrations.Migration):
    dependencies = [("ventas", "0007_venta_idx_venta_estado_fecha_and_more")]

    operations = [
        migrations.RunPython(completar_numeros, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="venta",
            name="numero_ticket",
            field=models.PositiveIntegerField(unique=True),
        ),
    ]
