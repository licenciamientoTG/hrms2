from django.urls import path
from .views import (
    user_dashboard,
    toggle_user_status,
    manage_user_permissions,
    admin_reset_password,
    create_group,
    delete_group,
    reset_password_to_default,
    terms_audit_view,
    user_inconsistencias_view,
    corregir_inconsistencia_view
)
from apps.users.views import force_password_change, upload_user_photo

urlpatterns = [
    path('admin/users/', user_dashboard, name='user_list'),
    path('admin/users/<int:user_id>/reset-password/', admin_reset_password, name='admin_reset_password'),
    path('', user_dashboard, name='user_dashboard'),
    path('toggle-user-status/', toggle_user_status, name='toggle_user_status'),
    path('manage/<int:user_id>/', manage_user_permissions, name='manage_user_permissions'),
    path('change-password/', force_password_change, name='force_password_change'),
    path('groups/create/', create_group, name='create_group'),
    path('groups/delete/<int:group_id>/', delete_group, name='delete_group'),
    path('reset-default/<int:user_id>/', reset_password_to_default, name='reset_password_default'),
    path('audit/terms/', terms_audit_view, name='terms_audit'),
    path('audit/inconsistencias/', user_inconsistencias_view, name='user_inconsistencias'),
    path('audit/inconsistencias/corregir/<int:emp_id>/', corregir_inconsistencia_view, name='corregir_inconsistencia'),
    path('upload-photo/<int:user_id>/', upload_user_photo, name='upload_user_photo'),
]
