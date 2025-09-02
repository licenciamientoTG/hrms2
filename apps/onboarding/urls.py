from django.urls import path
from .views import onboarding_dashboard, onboarding_dashboard_admin, onboarding_dashboard_user

urlpatterns = [
    path('', onboarding_dashboard, name='onboarding_dashboard'),
    path('admin/', onboarding_dashboard_admin, name='onboarding_dashboard_admin'),
    path('user/', onboarding_dashboard_user, name='onboarding_dashboard_user'),
]
