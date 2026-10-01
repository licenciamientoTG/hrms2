from django.urls import path
from .views import (
    vacation_dashboard,
    vacation_form_user,
    vacation_form_manager,
    vacation_form_rh,
    vacation_export_csv,
    vacation_cancel_user,
    vacation_edit_user,
    dias_festivos_api,
    dia_festivo_delete,
)

urlpatterns = [
    path('', vacation_dashboard, name='vacation_dashboard'),
    path('mis-solicitudes/', vacation_form_user, name='vacation_form_user'),
    path('mis-solicitudes/<int:pk>/cancelar/', vacation_cancel_user, name='vacation_cancel_user'),
    path('mis-solicitudes/<int:pk>/editar/', vacation_edit_user, name='vacation_edit_user'),
    path('gestion/', vacation_form_manager, name='vacation_form_manager'), # Manager (No admin)
    path('capital-humano/', vacation_form_rh, name='vacation_form_rh'),   # RH (Superuser)
    path('capital-humano/exportar/', vacation_export_csv, name='vacation_export_csv'),
    path('capital-humano/dias-festivos/', dias_festivos_api, name='dias_festivos_api'),
    path('capital-humano/dias-festivos/<int:pk>/', dia_festivo_delete, name='dia_festivo_delete'),
]