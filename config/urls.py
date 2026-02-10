from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/cash/', include('apps.cash.urls')),
    path('api/catalog/', include('apps.catalog.urls')),
    path('api/core/', include('apps.core.urls')),
    path('api/inventory/', include('apps.inventory.urls')),
    path('api/sales/', include('apps.sales.urls')),
    path('api/users/', include('apps.users.urls')),

]
