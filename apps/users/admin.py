from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User as DjangoUser

User = get_user_model()

# Desregistrar el User por defecto si ya está registrado
try:
    admin.site.unregister(DjangoUser)
except admin.sites.NotRegistered:
    pass

# Opcional: desregistrar Group y volver a registrarlo si querés personalizarlo después
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "is_superuser",
        "grupos_usuario",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "groups",
    )
    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )
    filter_horizontal = (
        "groups",
        "user_permissions",
    )

    @admin.display(description="Grupos")
    def grupos_usuario(self, obj):
        grupos = obj.groups.all()
        if not grupos:
            return "-"
        return ", ".join(g.name for g in grupos)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    pass