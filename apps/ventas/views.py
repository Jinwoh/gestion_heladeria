from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def pos_view(request):
    return render(request, "pos/pos.html")