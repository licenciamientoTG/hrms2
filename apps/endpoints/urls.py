from django.urls import path
from .views import recibir_datos1

urlpatterns = [
    path('recibir_datos1/', recibir_datos1),
]