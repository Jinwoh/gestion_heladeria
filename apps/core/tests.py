from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import Caja, CajaSesion
from apps.clientes.models import Cliente
from apps.productos.models import Categoria, Producto
from apps.ventas.models import Venta, VentaDetalle, VentaPago
from .models import ConfiguracionDashboard


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.vendedor = user_model.objects.create_user("vendedor", password="clave-segura")
        cls.otro_vendedor = user_model.objects.create_user("otro", password="clave-segura")
        cls.vendedor.user_permissions.add(Permission.objects.get(codename="view_venta"))

        categoria = Categoria.objects.create(nombre="Helados")
        cls.producto = Producto.objects.create(
            categoria=categoria,
            nombre="Cucurucho",
            precio=Decimal("1500"),
        )
        cls.cliente = Cliente.objects.create(
            nombre="Ana",
            documento="dashboard-001",
        )

        cls.venta_propia = cls._crear_venta(
            usuario=cls.vendedor,
            caja_numero="D01",
            total=Decimal("1500"),
            cliente=cls.cliente,
            metodo=VentaPago.MetodoPago.EFECTIVO,
        )
        cls.venta_ajena = cls._crear_venta(
            usuario=cls.otro_vendedor,
            caja_numero="D02",
            total=Decimal("2500"),
            metodo=VentaPago.MetodoPago.TARJETA,
        )

    @classmethod
    def _crear_venta(cls, *, usuario, caja_numero, total, metodo, cliente=None):
        caja = Caja.objects.create(numero=caja_numero)
        sesion = CajaSesion.objects.create(caja=caja, usuario=usuario)
        venta = Venta.objects.create(
            numero_ticket=None,
            caja_sesion=sesion,
            usuario=usuario,
            cliente=cliente,
            total=total,
        )
        VentaPago.objects.create(
            venta=venta,
            metodo_pago=metodo,
            monto=total,
            monto_recibido=total,
        )
        VentaDetalle.objects.create(
            venta=venta,
            producto=cls.producto,
            cantidad=1,
            precio_unitario=total,
            subtotal=total,
        )
        Venta.objects.filter(pk=venta.pk).update(fecha=timezone.now() - timedelta(days=1))
        venta.refresh_from_db()
        return venta

    def test_dashboard_requiere_autenticacion(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(response, f'{reverse("login")}?next={reverse("home")}')

    def test_vendedor_solo_ve_sus_ventas(self):
        self.client.force_login(self.vendedor)

        response = self.client.get(reverse("home"), {"period": "6m"})

        self.assertEqual(response.status_code, 200)
        dashboard = response.context["dashboard"]
        self.assertFalse(dashboard["globales"])
        self.assertEqual(dashboard["kpis"][0]["value"], Decimal("1500"))
        self.assertEqual(dashboard["kpis"][1]["value"], 1)
        self.assertEqual(dashboard["charts"]["payments"]["data"], [1500.0, 0.0, 0.0])
        self.assertEqual(sum(dashboard["charts"]["timeline"]["sales"]), 1500.0)
        self.assertEqual(sum(dashboard["charts"]["timeline"]["operations"]), 1)
        self.assertContains(response, "Cucurucho")
        self.assertContains(response, "Ventas a través del tiempo")
        self.assertNotContains(response, "Ventas con cliente identificado")

    def test_permiso_global_incluye_todos_los_vendedores(self):
        self.vendedor.user_permissions.add(
            Permission.objects.get(codename="view_global_reports")
        )
        self.client.force_login(self.vendedor)

        response = self.client.get(reverse("home"), {"period": "12m"})

        dashboard = response.context["dashboard"]
        self.assertTrue(dashboard["globales"])
        self.assertEqual(dashboard["kpis"][0]["value"], Decimal("4000"))
        self.assertEqual(len(dashboard["vendedores"]), 2)

    def test_periodo_invalido_usa_seis_meses(self):
        self.client.force_login(self.vendedor)

        response = self.client.get(reverse("home"), {"period": "invalido"})

        self.assertEqual(response.context["dashboard"]["periodo"], "6m")

    def test_usuario_sin_permiso_no_puede_modificar_meta(self):
        self.client.force_login(self.vendedor)

        response = self.client.post(
            reverse("actualizar_meta_dashboard"),
            {"meta_mensual": "7500000", "period": "6m"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ConfiguracionDashboard.objects.exists())
        self.assertNotContains(self.client.get(reverse("home")), "Editar meta")

    def test_usuario_autorizado_actualiza_meta_y_queda_registrado(self):
        permiso = Permission.objects.get(
            content_type__app_label="core",
            codename="change_configuraciondashboard",
        )
        self.vendedor.user_permissions.add(permiso)
        vendedor = get_user_model().objects.get(pk=self.vendedor.pk)
        self.client.force_login(vendedor)

        response = self.client.post(
            reverse("actualizar_meta_dashboard"),
            {"meta_mensual": "7500000", "period": "12m"},
        )

        self.assertRedirects(response, f'{reverse("home")}?period=12m')
        configuracion = ConfiguracionDashboard.objects.get(pk=1)
        self.assertEqual(configuracion.meta_mensual, Decimal("7500000"))
        self.assertEqual(configuracion.actualizada_por, vendedor)
        home = self.client.get(reverse("home"), {"period": "12m"})
        self.assertContains(home, "Editar meta")
        self.assertEqual(home.context["dashboard"]["meta_mensual"], Decimal("7500000"))

    def test_meta_invalida_no_se_guarda(self):
        permiso = Permission.objects.get(
            content_type__app_label="core",
            codename="change_configuraciondashboard",
        )
        self.vendedor.user_permissions.add(permiso)
        vendedor = get_user_model().objects.get(pk=self.vendedor.pk)
        self.client.force_login(vendedor)

        response = self.client.post(
            reverse("actualizar_meta_dashboard"),
            {"meta_mensual": "0", "period": "invalido"},
        )

        self.assertRedirects(response, f'{reverse("home")}?period=6m')
        self.assertFalse(ConfiguracionDashboard.objects.exists())
