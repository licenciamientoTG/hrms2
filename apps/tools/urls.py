from django.urls import path
from . import views

urlpatterns = [
    path('', views.calculator_view, name='calculator_view'),
    
    # Rutas específicas (NECESARIAS para que el redirect funcione)
    path('user/', views.calculator_user, name='calculator_user'),
    path('admin/', views.calculator_admin, name='calculator_admin'),
]