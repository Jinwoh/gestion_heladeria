from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = "Crea los grupos base del sistema: Cajero, Supervisor y Administrador"

    def handle(self, *args, **options):
        cajero, _ = Group.objects.get_or_create(name="Cajero")
        supervisor, _ = Group.objects.get_or_create(name="Supervisor")
        administrador, _ = Group.objects.get_or_create(name="Administrador")

        # Limpiar permisos anteriores para dejar configuración consistente
        cajero.permissions.clear()
        supervisor.permissions.clear()
        administrador.permissions.clear()

        def perms(codenames):
            return Permission.objects.filter(codename__in=codenames)

        # CAJERO
        cajero.permissions.add(*perms([
            "view_producto",
            "view_stock",
            "add_venta",
            "view_venta",
            "add_ventadetalle",
            "view_ventadetalle",
            "add_ventapago",
            "view_ventapago",
            "view_caja",
            "view_cajasesion",
            "add_cajasesion",
            "change_cajasesion",
            "view_movimientocaja",
            "add_movimientocaja",
        ]))

        # SUPERVISOR
        supervisor.permissions.add(*perms([
            "view_producto",
            "add_producto",
            "change_producto",
            "view_stock",
            "change_stock",
            "view_venta",
            "add_venta",
            "change_venta",
            "view_ventadetalle",
            "view_ventapago",
            "view_caja",
            "view_cajasesion",
            "add_cajasesion",
            "change_cajasesion",
            "view_movimientocaja",
            "add_movimientocaja",
            "change_movimientocaja",
        ]))

        # ADMINISTRADOR
        administrador.permissions.set(Permission.objects.all())

        self.stdout.write(self.style.SUCCESS("Grupos base creados correctamente."))