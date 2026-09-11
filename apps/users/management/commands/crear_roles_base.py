from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = "Crea los grupos base del sistema: Cajero, Supervisor y Administrador"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina personalizaciones previas antes de aplicar los permisos base.",
        )

    def handle(self, *args, **options):
        cajero, _ = Group.objects.get_or_create(name="Cajero")
        supervisor, _ = Group.objects.get_or_create(name="Supervisor")
        administrador, _ = Group.objects.get_or_create(name="Administrador")

        if options["reset"]:
            cajero.permissions.clear()
            supervisor.permissions.clear()
            administrador.permissions.clear()

        def perms(*permisos):
            consulta = Permission.objects.none()
            for app_label, codename in permisos:
                consulta = consulta | Permission.objects.filter(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            return consulta

        # CAJERO
        cajero.permissions.add(*perms(
            ("productos", "view_producto"),
            ("inventario", "view_stock"),
            ("ventas", "add_venta"),
            ("ventas", "view_venta"),
            ("ventas", "add_ventadetalle"),
            ("ventas", "view_ventadetalle"),
            ("ventas", "add_ventapago"),
            ("ventas", "view_ventapago"),
            ("clientes", "view_cliente"),
            ("clientes", "add_cliente"),
            ("caja", "view_caja"),
            ("caja", "view_cajasesion"),
            ("caja", "add_cajasesion"),
            ("caja", "change_cajasesion"),
            ("caja", "view_movimientocaja"),
            ("caja", "add_movimientocaja"),
        ))

        # SUPERVISOR
        supervisor.permissions.add(*perms(
            ("productos", "view_producto"),
            ("productos", "add_producto"),
            ("productos", "change_producto"),
            ("inventario", "view_stock"),
            ("inventario", "change_stock"),
            ("inventario", "view_movimientostock"),
            ("ventas", "view_venta"),
            ("ventas", "add_venta"),
            ("ventas", "view_global_reports"),
            ("ventas", "cancel_venta"),
            ("ventas", "view_ventadetalle"),
            ("ventas", "view_ventapago"),
            ("clientes", "view_cliente"),
            ("clientes", "add_cliente"),
            ("clientes", "change_cliente"),
            ("caja", "view_caja"),
            ("caja", "view_cajasesion"),
            ("caja", "add_cajasesion"),
            ("caja", "change_cajasesion"),
            ("caja", "view_movimientocaja"),
            ("caja", "add_movimientocaja"),
        ))

        # ADMINISTRADOR
        administrador.permissions.set(Permission.objects.all())

        self.stdout.write(self.style.SUCCESS("Grupos base creados correctamente."))
