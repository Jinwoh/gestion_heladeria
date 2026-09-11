from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.caja.models import Caja, CajaSesion, MovimientoCaja
from apps.caja.services import abrir_caja
from apps.inventario.models import Stock
from apps.productos.models import Categoria, Producto

from .models import Venta, VentaPago
from .services import anular_venta, crear_venta


class VentaServiceTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("cajero", password="segura-123")
        self.caja = Caja.objects.create(numero="1")
        self.caja.usuarios_habilitados.add(self.usuario)
        self.sesion = abrir_caja(
            usuario=self.usuario, caja=self.caja, monto_apertura=Decimal("50.00")
        )
        categoria = Categoria.objects.create(nombre="Helados")
        self.producto = Producto.objects.create(
            categoria=categoria, nombre="Chocolate", precio=Decimal("100.00")
        )
        Stock.objects.filter(producto=self.producto).update(cantidad=10)

    def test_venta_con_vuelto_guarda_importes_netos(self):
        venta = crear_venta(
            usuario=self.usuario,
            items=[{"producto_id": self.producto.id, "cantidad": 1}],
            pagos=[{"metodo_pago": "efectivo", "monto": "120.00"}],
        )

        pago = venta.pagos.get()
        movimiento = self.sesion.movimientos.get(tipo=MovimientoCaja.Tipo.VENTA)
        self.assertEqual(venta.total, Decimal("100.00"))
        self.assertEqual(venta.vuelto, Decimal("20.00"))
        self.assertEqual(pago.monto, Decimal("100.00"))
        self.assertEqual(pago.monto_recibido, Decimal("120.00"))
        self.assertEqual(movimiento.monto, Decimal("100.00"))
        self.assertEqual(Stock.objects.get(producto=self.producto).cantidad, 9)

    def test_rechaza_pago_electronico_superior_y_revierte(self):
        with self.assertRaises(ValidationError):
            crear_venta(
                usuario=self.usuario,
                items=[{"producto_id": self.producto.id, "cantidad": 1}],
                pagos=[{"metodo_pago": "tarjeta", "monto": "120.00"}],
            )

        self.assertFalse(Venta.objects.exists())
        self.assertEqual(Stock.objects.get(producto=self.producto).cantidad, 10)

    def test_agrupa_productos_repetidos(self):
        venta = crear_venta(
            usuario=self.usuario,
            items=[
                {"producto_id": self.producto.id, "cantidad": 1},
                {"producto_id": self.producto.id, "cantidad": 2},
            ],
            pagos=[{"metodo_pago": "qr", "monto": "300.00"}],
        )
        self.assertEqual(venta.detalles.count(), 1)
        self.assertEqual(venta.detalles.get().cantidad, 3)

    def test_cliente_nuevo_se_revierte_si_falla_la_venta(self):
        from apps.clientes.models import Cliente

        with self.assertRaises(ValidationError):
            crear_venta(
                usuario=self.usuario,
                items=[{"producto_id": self.producto.id, "cantidad": 99}],
                pagos=[{"metodo_pago": "efectivo", "monto": "9900.00"}],
                cliente_data={"nombre": "Ana", "documento": "123", "activo": True},
            )
        self.assertFalse(Cliente.objects.filter(documento="123").exists())

    def test_anulacion_restituye_stock_y_genera_contramovimiento(self):
        venta = crear_venta(
            usuario=self.usuario,
            items=[{"producto_id": self.producto.id, "cantidad": 2}],
            pagos=[{"metodo_pago": "efectivo", "monto": "200.00"}],
        )
        anular_venta(venta=venta, usuario=self.usuario, motivo="Carga duplicada")

        venta.refresh_from_db()
        self.assertEqual(venta.estado, Venta.Estado.ANULADA)
        self.assertEqual(Stock.objects.get(producto=self.producto).cantidad, 10)
        self.assertTrue(
            self.sesion.movimientos.filter(tipo=MovimientoCaja.Tipo.ANULACION).exists()
        )

    def test_no_anula_venta_de_caja_cerrada(self):
        venta = crear_venta(
            usuario=self.usuario,
            items=[{"producto_id": self.producto.id, "cantidad": 1}],
            pagos=[{"metodo_pago": "efectivo", "monto": "100.00"}],
        )
        CajaSesion.objects.filter(pk=self.sesion.pk).update(
            estado=CajaSesion.Estado.CERRADA,
            fecha_cierre=timezone.now(),
            monto_cierre_declarado=Decimal("150.00"),
        )
        with self.assertRaises(ValidationError):
            anular_venta(venta=venta, usuario=self.usuario, motivo="Error")

    def test_tickets_secuenciales(self):
        ventas = []
        for _ in range(2):
            ventas.append(
                crear_venta(
                    usuario=self.usuario,
                    items=[{"producto_id": self.producto.id, "cantidad": 1}],
                    pagos=[{"metodo_pago": "efectivo", "monto": "100.00"}],
                )
            )
        self.assertEqual(ventas[1].numero_ticket, ventas[0].numero_ticket + 1)

    def test_importe_con_mas_de_dos_decimales_es_invalido(self):
        with self.assertRaises(ValidationError):
            crear_venta(
                usuario=self.usuario,
                items=[{"producto_id": self.producto.id, "cantidad": 1}],
                pagos=[{"metodo_pago": VentaPago.MetodoPago.EFECTIVO, "monto": "100.001"}],
            )
