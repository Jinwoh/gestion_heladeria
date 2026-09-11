from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import Caja, CajaSesion, MovimientoCaja
from apps.ventas.models import Venta

from .selectors import cierres_caja_qs


class ReportesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user("cajero")
        self.otro = User.objects.create_user("otro")
        self.caja = Caja.objects.create(numero="R1")
        self.sesion = CajaSesion.objects.create(
            caja=self.caja,
            usuario=self.usuario,
            estado=CajaSesion.Estado.CERRADA,
            monto_apertura=Decimal("0"),
            fecha_cierre=timezone.now(),
            monto_cierre_declarado=Decimal("0"),
        )
        self.otra_caja = Caja.objects.create(numero="R2")
        self.otra_sesion = CajaSesion.objects.create(
            caja=self.otra_caja,
            usuario=self.otro,
            estado=CajaSesion.Estado.CERRADA,
            monto_apertura=Decimal("0"),
            fecha_cierre=timezone.now(),
            monto_cierre_declarado=Decimal("0"),
        )
        self.venta_propia = Venta.objects.create(
            caja_sesion=self.sesion, usuario=self.usuario, total=Decimal("10")
        )
        self.venta_ajena = Venta.objects.create(
            caja_sesion=self.otra_sesion, usuario=self.otro, total=Decimal("20")
        )

    def test_cierre_no_multiplica_sumatorias_por_joins(self):
        Venta.objects.create(
            caja_sesion=self.sesion, usuario=self.usuario, total=Decimal("20")
        )
        for monto in (Decimal("3"), Decimal("4")):
            MovimientoCaja.objects.create(
                caja_sesion=self.sesion,
                usuario=self.usuario,
                tipo=MovimientoCaja.Tipo.INGRESO,
                monto=monto,
            )
        cierre = cierres_caja_qs().get(pk=self.sesion.pk)
        self.assertEqual(cierre.total_ventas, Decimal("30"))
        self.assertEqual(cierre.total_ingresos, Decimal("7"))

    def test_permiso_normal_solo_ve_ventas_propias(self):
        self.usuario.user_permissions.add(Permission.objects.get(codename="view_venta"))
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("reportes:reporte_dia"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["ventas"]), [self.venta_propia])

    def test_permiso_global_ve_todas_las_ventas(self):
        self.usuario.user_permissions.add(
            Permission.objects.get(codename="view_venta"),
            Permission.objects.get(codename="view_global_reports"),
        )
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("reportes:reporte_dia"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["ventas"]), 2)
