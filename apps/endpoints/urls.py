from django.urls import path
from .views import recibir_datos1, recibir_faltas

urlpatterns = [
    path('recibir_datos1/', recibir_datos1),
    path('recibir_faltas/', recibir_faltas),
]