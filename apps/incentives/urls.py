from django.urls import path
from .views import (
    incentives_dashboard,
    incentives_dashboard_admin,
    incentives_dashboard_zona,
    incentives_dashboard_user,
    incentives_dashboard_manager,
    incentives_dashboard_operaciones,
    parsear_excel_ventas,
    guardar_presupuesto_ventas,
    toggle_incentivo,
    toggle_semana_cerrada,
    semana_data,
    guardar_comentario,
    resumen_global,
)

urlpatterns = [
    path('', incentives_dashboard, name='incentives_dashboard'),
    path('admin/', incentives_dashboard_admin, name='incentives_dashboard_admin'),
    path('zona/', incentives_dashboard_zona, name='incentives_dashboard_zona'),
    path('manager/', incentives_dashboard_manager, name='incentives_dashboard_manager'),
    path('operaciones/', incentives_dashboard_operaciones, name='incentives_dashboard_operaciones'),
    path('user/', incentives_dashboard_user, name='incentives_dashboard_user'),
    path('toggle/', toggle_incentivo, name='toggle_incentivo'),
    path('cerrar-semana/', toggle_semana_cerrada, name='toggle_semana_cerrada'),
    path('semana/', semana_data, name='semana_data'),
    path('comentario/', guardar_comentario, name='guardar_comentario'),
    path('resumen-global/', resumen_global, name='resumen_global'),
    path('parsear-excel-ventas/', parsear_excel_ventas, name='parsear_excel_ventas'),
    path('guardar-presupuesto-ventas/', guardar_presupuesto_ventas, name='guardar_presupuesto_ventas'),
]
