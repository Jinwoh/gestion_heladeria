from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.productos.models import Categoria, Producto

from .models import MovimientoStock, Stock
from .services import ajustar_stock, restar_stock, sumar_stock


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
