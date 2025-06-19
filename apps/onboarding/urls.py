from django.urls import path
from .views import onboarding_dashboard_view

urlpatterns = [
    path('', onboarding_dashboard_view, name='onboarding_dashboard'),
]
