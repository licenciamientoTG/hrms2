from django.urls import path
from .views import user_dashboard, toggle_user_status, manage_user_permissions, upload_employees_csv

urlpatterns = [
    path('', user_dashboard, name='user_dashboard'),
    path('toggle-user-status/', toggle_user_status, name='toggle_user_status'),
    path('manage/<int:user_id>/', manage_user_permissions, name='manage_user_permissions'),
    path('upload-employees-csv/', upload_employees_csv, name='upload_employees_csv'),
]
