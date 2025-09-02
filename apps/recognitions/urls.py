from django.urls import path
from .views import recognition_dashboard, recognition_dashboard_admin, recognition_dashboard_user, recognition_dashboard

urlpatterns = [
    path('', recognition_dashboard, name='recognition_dashboard'),
    path('admin/', recognition_dashboard_admin, name='recognition_dashboard_admin'),
    path('user/', recognition_dashboard_user, name='recognition_dashboard_user'),
]
