from django.contrib import admin

from .models import ConfiguracionDashboard


@admin.register(ConfiguracionDashboard)
class ConfiguracionDashboardAdmin(admin.ModelAdmin):
    list_display = ("meta_mensual", "actualizada_por", "actualizada_en")
    readonly_fields = ("actualizada_por", "actualizada_en")

    def has_add_permission(self, request):
        return not ConfiguracionDashboard.objects.exists() and super().has_add_permission(request)

    def save_model(self, request, obj, form, change):
        obj.actualizada_por = request.user
        super().save_model(request, obj, form, change)
