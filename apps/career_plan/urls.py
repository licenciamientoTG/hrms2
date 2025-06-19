from django.urls import path
from .views import career_plan_dashboard_view

urlpatterns = [
    path('', career_plan_dashboard_view, name='career_plan_dashboard'),
]
