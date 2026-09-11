from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import Cliente


class ClienteViewTests(TestCase):
    def test_lista_renderiza_la_plantilla_existente(self):
        usuario = get_user_model().objects.create_user("consulta")
        usuario.user_permissions.add(Permission.objects.get(codename="view_cliente"))
        Cliente.objects.create(nombre="Ana", documento="123")
        self.client.force_login(usuario)

        response = self.client.get(reverse("clientes:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana")
