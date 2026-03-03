from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def apertura_caja(request):
    return render(request, "caja/apertura.html")

@login_required
def arqueo_caja(request):
    return render(request, "caja/arqueo.html")

@login_required
def cierre_caja(request):
    return render(request, "caja/cierre.html")