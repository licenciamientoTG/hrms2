from django.urls import path
from .views import objective_dashboard_view

urlpatterns = [
    path('', objective_dashboard_view, name='objective_dashboard'),
]
