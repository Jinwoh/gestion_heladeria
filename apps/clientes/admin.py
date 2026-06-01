from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellido", "documento", "telefono", "email", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "apellido", "documento", "telefono", "email")