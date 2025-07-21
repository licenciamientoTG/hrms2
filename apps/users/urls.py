from django.urls import path
from .views import (
    user_dashboard,
    toggle_user_status,
    manage_user_permissions,
    upload_employees_csv,
    admin_reset_password,
    crear_grupo,
)
from apps.users.views import force_password_change

urlpatterns = [
    path('admin/users/', user_dashboard, name='user_list'),
    path('admin/users/<int:user_id>/reset-password/',
         admin_reset_password,
         name='admin_reset_password'),
    path('', user_dashboard, name='user_dashboard'),
    path('toggle-user-status/', toggle_user_status, name='toggle_user_status'),
    path('manage/<int:user_id>/', manage_user_permissions, name='manage_user_permissions'),
    path('upload-employees-csv/', upload_employees_csv, name='upload_employees_csv'),
    path('grupos/crear/', crear_grupo, name='crear_grupo'),
    path('change-password/', force_password_change, name='force_password_change'),
]
