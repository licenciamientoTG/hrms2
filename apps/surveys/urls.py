from django.urls import path
from .views import survey_dashboard_view

urlpatterns = [
    path('', survey_dashboard_view, name='survey_dashboard'),
]
