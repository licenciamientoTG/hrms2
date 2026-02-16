from django.urls import path
from . import views

urlpatterns = [
    path('', views.calculator_view, name='calculator_view'),
    
    # Rutas específicas (NECESARIAS para que el redirect funcione)
    path('user/', views.calculator_user, name='calculator_user'),
    path('admin/', views.calculator_admin, name='calculator_admin'),
    path('api/create-loan/', views.create_loan_request, name='create_loan_request'),
    path('admin/export-excel/', views.export_loans_excel, name='export_loans_excel'),
    path('admin/prestamos/cancelar/<int:pk>/', views.cancel_loan_request, name='cancel_loan_request'),
]