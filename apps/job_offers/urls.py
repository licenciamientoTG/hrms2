from django.urls import path
from .views import job_offers_dashboard, job_offers_dashboard_admin, job_offers_dashboard_user

urlpatterns = [
    path('', job_offers_dashboard, name='job_offers_dashboard'),
    path('admin/', job_offers_dashboard_admin, name='job_offers_dashboard_admin'),
    path('user/', job_offers_dashboard_user, name='job_offers_dashboard_user'),
]
