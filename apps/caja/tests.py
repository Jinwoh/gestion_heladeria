from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from .models import Caja, CajaSesion, MovimientoCaja
from .services import abrir_caja, registrar_movimiento, resumen_caja


class CajaServiceTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("operador")
        self.caja = Caja.objects.create(numero="01")
        self.caja.usuarios_habilitados.add(self.usuario)

    def test_no_abre_dos_cajas_para_un_usuario(self):
        abrir_caja(usuario=self.usuario, caja=self.caja, monto_apertura=Decimal("0"))
        otra = Caja.objects.create(numero="02")
        otra.usuarios_habilitados.add(self.usuario)
        with self.assertRaises(ValidationError):
            abrir_caja(usuario=self.usuario, caja=otra, monto_apertura=Decimal("0"))

    def test_restriccion_impide_dos_sesiones_abiertas_por_caja(self):
        abrir_caja(usuario=self.usuario, caja=self.caja, monto_apertura=Decimal("0"))
        otro = get_user_model().objects.create_user("otro")
        with self.assertRaises(IntegrityError):
            CajaSesion.objects.create(caja=self.caja, usuario=otro)

    def test_ajustes_afectan_el_esperado(self):
        sesion = abrir_caja(
            usuario=self.usuario, caja=self.caja, monto_apertura=Decimal("100")
        )
        registrar_movimiento(
            caja=sesion,
            usuario=self.usuario,
            tipo=MovimientoCaja.Tipo.AJUSTE_INGRESO,
            monto=Decimal("10"),
            motivo="Sobrante",
        )
        registrar_movimiento(
            caja=sesion,
            usuario=self.usuario,
            tipo=MovimientoCaja.Tipo.AJUSTE_EGRESO,
            monto=Decimal("5"),
            motivo="Faltante",
        )
        self.assertEqual(resumen_caja(sesion)["esperado"], Decimal("105"))

    def test_no_permite_tipo_venta_como_movimiento_manual(self):
        sesion = abrir_caja(
            usuario=self.usuario, caja=self.caja, monto_apertura=Decimal("0")
        )
        with self.assertRaises(ValidationError):
            registrar_movimiento(
                caja=sesion,
                usuario=self.usuario,
                tipo=MovimientoCaja.Tipo.VENTA,
                monto=Decimal("10"),
            )
