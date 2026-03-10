from django.urls import path
from . import views

app_name = "ventas"

urlpatterns = [
    path("", views.pos_view, name="pos"),  # /pos/
    
]