from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render


@login_required
@permission_required("productos.view_producto", raise_exception=True)
def productos_view(request):
    return render(request, "productos/productos.html")