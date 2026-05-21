from django.urls import path
from .views import incentives_dashboard, incentives_dashboard_admin, incentives_dashboard_user

urlpatterns = [
    path('', incentives_dashboard, name='incentives_dashboard'),
    path('admin/', incentives_dashboard_admin, name='incentives_dashboard_admin'),
    path('user/', incentives_dashboard_user, name='incentives_dashboard_user'),
]
