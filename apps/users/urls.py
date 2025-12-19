from django.urls import path
from .views import (
    user_dashboard,
    toggle_user_status,
    manage_user_permissions,
    admin_reset_password,
    create_group,
    delete_group,
)
from apps.users.views import force_password_change

urlpatterns = [
    path('admin/users/', user_dashboard, name='user_list'),
    path('admin/users/<int:user_id>/reset-password/', admin_reset_password, name='admin_reset_password'),
    path('', user_dashboard, name='user_dashboard'),
    path('toggle-user-status/', toggle_user_status, name='toggle_user_status'),
    path('manage/<int:user_id>/', manage_user_permissions, name='manage_user_permissions'),
    path('change-password/', force_password_change, name='force_password_change'),
    path('groups/create/', create_group, name='create_group'),
    path('groups/delete/<int:group_id>/', delete_group, name='delete_group'),
]
