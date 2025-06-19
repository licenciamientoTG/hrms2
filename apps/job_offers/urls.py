from django.urls import path
from .views import job_offers_dashboard_view

urlpatterns = [
    path('', job_offers_dashboard_view, name='job_offers_dashboard'),
]
