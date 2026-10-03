from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.productos.models import Categoria, Producto, UnidadMedida

from .models import DetalleOrdenCompra, DetalleRecepcionCompra, MovimientoStock, OrdenCompra, Proveedor, RecepcionCompra, Stock
from .services import ajustar_stock, emitir_orden, registrar_recepcion, restar_stock, sumar_stock


class InventarioServiceTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("deposito")
        categoria = Categoria.objects.create(nombre="Postres")
        self.producto = Producto.objects.create(categoria=categoria, nombre="Torta", precio=10)

    def test_producto_nuevo_crea_stock(self):
        self.assertTrue(Stock.objects.filter(producto=self.producto, cantidad=0).exists())

    def test_operaciones_de_stock_dejan_auditoria(self):
        sumar_stock(producto=self.producto, cantidad=5, usuario=self.usuario, motivo="Compra")
        restar_stock(producto=self.producto, cantidad=2, usuario=self.usuario, motivo="Uso")
        ajustar_stock(producto=self.producto, nueva_cantidad=4, usuario=self.usuario, motivo="Conteo")
        self.assertEqual(Stock.objects.get(producto=self.producto).cantidad, 4)
        self.assertEqual(MovimientoStock.objects.filter(producto=self.producto).count(), 3)

    def test_no_permite_stock_negativo(self):
        with self.assertRaises(ValidationError):
            restar_stock(producto=self.producto, cantidad=1, usuario=self.usuario)


class InventarioViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            "admin-inventario",
            password="segura-123",
        )
        categoria = Categoria.objects.create(nombre="Bebidas")
        self.producto = Producto.objects.create(
            categoria=categoria,
            nombre="Agua mineral",
            precio=5000,
        )
        self.client.force_login(self.usuario)

    def test_inventario_ya_no_muestra_formulario_de_movimiento(self):
        response = self.client.get(reverse("inventario:stock"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Movimiento auditado")
        self.assertNotContains(response, "Guardar movimiento")

    def test_modulo_independiente_muestra_formulario(self):
        response = self.client.get(reverse("inventario:movimiento"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ajuste de stock")
        self.assertContains(response, "Registrar ajuste")

    def test_modulo_expone_stock_actual_para_actualizacion_dinamica(self):
        Stock.objects.filter(producto=self.producto).update(cantidad=12)

        response = self.client.get(reverse("inventario:movimiento"))

        self.assertEqual(
            response.context["stock_por_producto"][str(self.producto.id)]["stock"],
            "12.000",
        )
        self.assertContains(response, 'id="stock-actual-valor"')
        self.assertContains(response, 'id="stock-por-producto"')
        self.assertContains(response, "js/inventario-movimiento.js")

    def test_ajuste_desde_nuevo_modulo_actualiza_y_audita(self):
        response = self.client.post(
            reverse("inventario:movimiento"),
            {
                "producto": self.producto.id,
                "cantidad": 7,
                "motivo": "Conteo físico",
            },
        )

        self.assertRedirects(response, reverse("inventario:movimiento"))
        self.assertEqual(Stock.objects.get(producto=self.producto).cantidad, 7)
        self.assertTrue(
            MovimientoStock.objects.filter(
                producto=self.producto,
                cantidad=7,
                motivo="Conteo físico",
                usuario=self.usuario,
                tipo=MovimientoStock.Tipo.AJUSTE_POSITIVO,
            ).exists()
        )


class ComprasInventarioTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("compras")
        self.categoria = Categoria.objects.create(nombre="Compras")
        self.unidad = UnidadMedida.objects.get(abreviatura="un")
        self.kg = UnidadMedida.objects.create(nombre="Kilogramo test", abreviatura="kg-test", permite_decimales=True)
        self.reventa = Producto.objects.create(categoria=self.categoria, nombre="Gaseosa", precio=5000, tipo=Producto.Tipo.PRODUCTO_REVENTA, unidad_medida=self.unidad)
        self.insumo = Producto.objects.create(categoria=self.categoria, nombre="Azúcar", precio=0, tipo=Producto.Tipo.INSUMO, unidad_medida=self.kg)
        self.elaborado = Producto.objects.create(categoria=self.categoria, nombre="Helado", precio=10000, tipo=Producto.Tipo.PRODUCTO_ELABORADO, unidad_medida=self.kg)
        self.proveedor = Proveedor.objects.create(razon_social="Distribuidora ABC", ruc="80000000-1")

    def crear_orden(self, producto=None, cantidad="10", tipo=None):
        producto = producto or self.insumo
        orden = OrdenCompra.objects.create(proveedor=self.proveedor, tipo=tipo or producto.tipo, fecha=date.today(), creado_por=self.usuario)
        detalle = DetalleOrdenCompra.objects.create(orden_compra=orden, producto=producto, cantidad_solicitada=Decimal(cantidad), unidad_medida=producto.unidad_medida, costo_unitario=Decimal("2500"))
        return orden, detalle

    def test_crear_oc_no_modifica_stock(self):
        self.crear_orden()
        self.assertEqual(self.insumo.stock.cantidad, 0)
        self.assertFalse(MovimientoStock.objects.filter(producto=self.insumo).exists())

    def test_recepcion_completa_aumenta_stock_y_genera_movimiento(self):
        orden, detalle = self.crear_orden(cantidad="10.500")
        emitir_orden(orden, usuario=self.usuario)
        recepcion, creada = registrar_recepcion(orden=orden, cantidades={detalle.pk: "10.500"}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())
        self.assertTrue(creada)
        self.insumo.stock.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(self.insumo.stock.cantidad, Decimal("10.500"))
        self.assertEqual(orden.estado, OrdenCompra.Estado.RECIBIDA)
        movimiento = MovimientoStock.objects.get(producto=self.insumo)
        self.assertEqual(movimiento.tipo, MovimientoStock.Tipo.ENTRADA_COMPRA)
        self.assertEqual(movimiento.stock_anterior, 0)
        self.assertEqual(movimiento.stock_resultante, Decimal("10.500"))
        self.assertEqual(movimiento.detalle_recepcion.recepcion, recepcion)

    def test_recepcion_parcial_y_posterior_completan_pendiente(self):
        orden, detalle = self.crear_orden(cantidad="100")
        emitir_orden(orden, usuario=self.usuario)
        registrar_recepcion(orden=orden, cantidades={detalle.pk: "80"}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())
        orden.refresh_from_db(); self.insumo.stock.refresh_from_db()
        self.assertEqual(orden.estado, OrdenCompra.Estado.PARCIALMENTE_RECIBIDA)
        self.assertEqual(self.insumo.stock.cantidad, 80)
        registrar_recepcion(orden=orden, cantidades={detalle.pk: "20"}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())
        orden.refresh_from_db(); self.insumo.stock.refresh_from_db()
        self.assertEqual(orden.estado, OrdenCompra.Estado.RECIBIDA)
        self.assertEqual(self.insumo.stock.cantidad, 100)
        self.assertEqual(RecepcionCompra.objects.filter(orden_compra=orden).count(), 2)

    def test_oc_insumo_no_acepta_reventa(self):
        orden, _ = self.crear_orden()
        detalle = DetalleOrdenCompra(orden_compra=orden, producto=self.reventa, cantidad_solicitada=1, unidad_medida=self.unidad, costo_unitario=1)
        with self.assertRaises(ValidationError): detalle.full_clean()

    def test_oc_reventa_no_acepta_insumo(self):
        orden = OrdenCompra.objects.create(proveedor=self.proveedor, tipo=Producto.Tipo.PRODUCTO_REVENTA, fecha=date.today(), creado_por=self.usuario)
        detalle = DetalleOrdenCompra(orden_compra=orden, producto=self.insumo, cantidad_solicitada=1, unidad_medida=self.kg, costo_unitario=1)
        with self.assertRaises(ValidationError): detalle.full_clean()

    def test_producto_elaborado_no_se_compra(self):
        orden = OrdenCompra.objects.create(proveedor=self.proveedor, tipo=Producto.Tipo.INSUMO, fecha=date.today(), creado_por=self.usuario)
        detalle = DetalleOrdenCompra(orden_compra=orden, producto=self.elaborado, cantidad_solicitada=1, unidad_medida=self.kg, costo_unitario=1)
        with self.assertRaises(ValidationError): detalle.full_clean()

    def test_no_recibir_oc_cancelada(self):
        orden, detalle = self.crear_orden(); orden.estado = OrdenCompra.Estado.CANCELADA; orden.save()
        with self.assertRaises(ValidationError): registrar_recepcion(orden=orden, cantidades={detalle.pk: 1}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())

    def test_no_recibir_oc_totalmente_recibida(self):
        orden, detalle = self.crear_orden(cantidad=1); emitir_orden(orden, usuario=self.usuario)
        registrar_recepcion(orden=orden, cantidades={detalle.pk: 1}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())
        with self.assertRaises(ValidationError): registrar_recepcion(orden=orden, cantidades={detalle.pk: 1}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())

    def test_no_permite_sobre_recepcion(self):
        orden, detalle = self.crear_orden(cantidad=5); emitir_orden(orden, usuario=self.usuario)
        with self.assertRaises(ValidationError): registrar_recepcion(orden=orden, cantidades={detalle.pk: 6}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())

    def test_ajustes_positivo_y_negativo_generan_movimientos(self):
        ajustar_stock(producto=self.insumo, nueva_cantidad=10, usuario=self.usuario, motivo="Conteo inicial")
        ajustar_stock(producto=self.insumo, nueva_cantidad=8, usuario=self.usuario, motivo="Merma")
        self.insumo.stock.refresh_from_db()
        self.assertEqual(self.insumo.stock.cantidad, 8)
        self.assertTrue(MovimientoStock.objects.filter(producto=self.insumo, tipo=MovimientoStock.Tipo.AJUSTE_POSITIVO, cantidad=10).exists())
        self.assertTrue(MovimientoStock.objects.filter(producto=self.insumo, tipo=MovimientoStock.Tipo.AJUSTE_NEGATIVO, cantidad=-2).exists())

    def test_rollback_si_falla_recepcion(self):
        orden, detalle = self.crear_orden(); emitir_orden(orden, usuario=self.usuario)
        with patch("apps.inventario.services.registrar_movimiento", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError): registrar_recepcion(orden=orden, cantidades={detalle.pk: 5}, usuario=self.usuario, clave_idempotencia=uuid.uuid4())
        self.insumo.stock.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(self.insumo.stock.cantidad, 0)
        self.assertFalse(RecepcionCompra.objects.filter(orden_compra=orden).exists())
        self.assertEqual(orden.estado, OrdenCompra.Estado.EMITIDA)

    def test_clave_idempotente_no_duplica_recepcion_ni_stock(self):
        orden, detalle = self.crear_orden(); emitir_orden(orden, usuario=self.usuario)
        clave = uuid.uuid4()
        primera, creada = registrar_recepcion(orden=orden, cantidades={detalle.pk: 4}, usuario=self.usuario, clave_idempotencia=clave)
        segunda, creada_segunda = registrar_recepcion(orden=orden, cantidades={detalle.pk: 4}, usuario=self.usuario, clave_idempotencia=clave)
        self.insumo.stock.refresh_from_db()
        self.assertTrue(creada); self.assertFalse(creada_segunda)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(self.insumo.stock.cantidad, 4)
        self.assertEqual(MovimientoStock.objects.filter(producto=self.insumo).count(), 1)

    def test_pantallas_nuevas_y_creacion_de_oc(self):
        admin = get_user_model().objects.create_superuser("admin-compras", password="segura-123")
        self.client.force_login(admin)
        for url in [
            reverse("inventario:proveedores"),
            reverse("inventario:ordenes"),
            reverse("inventario:recepciones"),
            reverse("inventario:movimientos"),
            reverse("productos:lista"),
            reverse("inventario:orden_crear"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)

        response = self.client.post(reverse("inventario:orden_crear"), {
            "proveedor": self.proveedor.pk,
            "tipo": Producto.Tipo.INSUMO,
            "fecha": date.today().isoformat(),
            "fecha_estimada_entrega": "",
            "observaciones": "Compra semanal",
            "detalles-TOTAL_FORMS": "1",
            "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "0",
            "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-producto": self.insumo.pk,
            "detalles-0-cantidad_solicitada": "25.500",
            "detalles-0-unidad_medida": self.kg.pk,
            "detalles-0-costo_unitario": "3000",
        })
        self.assertEqual(response.status_code, 302)
        orden = OrdenCompra.objects.latest("pk")
        self.assertEqual(orden.estado, OrdenCompra.Estado.BORRADOR)
        self.assertEqual(orden.detalles.get().cantidad_solicitada, Decimal("25.500"))
        self.insumo.stock.refresh_from_db()
        self.assertEqual(self.insumo.stock.cantidad, 0)
