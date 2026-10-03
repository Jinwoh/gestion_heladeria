import django.db.models.deletion
from django.db import migrations, models


UNIDADES = [
    ("Unidad", "un", False),
    ("Kilogramo", "kg", True),
    ("Gramo", "g", True),
    ("Litro", "l", True),
    ("Mililitro", "ml", True),
    ("Caja", "caja", False),
    ("Bolsa", "bolsa", False),
    ("Paquete", "paq", False),
]


def preparar_catalogo(apps, schema_editor):
    UnidadMedida = apps.get_model("productos", "UnidadMedida")
    Producto = apps.get_model("productos", "Producto")
    unidad_base = None
    for nombre, abreviatura, permite_decimales in UNIDADES:
        unidad, _ = UnidadMedida.objects.get_or_create(
            abreviatura=abreviatura,
            defaults={"nombre": nombre, "permite_decimales": permite_decimales, "activa": True},
        )
        if abreviatura == "un":
            unidad_base = unidad
    Producto.objects.filter(unidad_medida__isnull=True).update(
        unidad_medida=unidad_base,
        tipo="PRODUCTO_REVENTA",
    )


class Migration(migrations.Migration):
    dependencies = [("productos", "0003_remove_producto_ck_producto_precio_no_negativo_and_more")]

    operations = [
        migrations.CreateModel(
            name="UnidadMedida",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80, unique=True)),
                ("abreviatura", models.CharField(max_length=12, unique=True)),
                ("permite_decimales", models.BooleanField(default=False)),
                ("activa", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Unidad de medida", "verbose_name_plural": "Unidades de medida", "ordering": ["nombre"]},
        ),
        migrations.RemoveConstraint(model_name="producto", name="ck_producto_precio_positivo"),
        migrations.AddField(
            model_name="producto", name="tipo",
            field=models.CharField(choices=[("PRODUCTO_REVENTA", "Producto de reventa"), ("INSUMO", "Insumo"), ("PRODUCTO_ELABORADO", "Producto elaborado")], db_index=True, default="PRODUCTO_REVENTA", max_length=24),
        ),
        migrations.AddField(model_name="producto", name="stock_minimo", field=models.DecimalField(decimal_places=3, default=0, max_digits=14)),
        migrations.AddField(model_name="producto", name="ultimo_costo", field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
        migrations.AddField(
            model_name="producto", name="unidad_medida",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="productos", to="productos.unidadmedida"),
        ),
        migrations.RunPython(preparar_catalogo, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="producto", name="unidad_medida",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="productos", to="productos.unidadmedida"),
        ),
        migrations.AddConstraint(
            model_name="producto",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("precio__gte", 0), ("tipo", "INSUMO")), models.Q(("precio__gt", 0), ("tipo__in", ["PRODUCTO_REVENTA", "PRODUCTO_ELABORADO"])), _connector="OR"), name="ck_producto_precio_segun_tipo"),
        ),
        migrations.AddConstraint(model_name="producto", constraint=models.CheckConstraint(condition=models.Q(("stock_minimo__gte", 0)), name="ck_producto_stock_minimo_no_negativo")),
        migrations.AddConstraint(model_name="producto", constraint=models.CheckConstraint(condition=models.Q(("ultimo_costo__isnull", True), ("ultimo_costo__gte", 0), _connector="OR"), name="ck_producto_ultimo_costo_no_negativo")),
    ]
