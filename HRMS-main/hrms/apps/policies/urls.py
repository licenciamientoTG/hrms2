from django.urls import path
from .views import policies_dashboard_view

urlpatterns = [
    path('', policies_dashboard_view, name='policies_dashboard'),
]
