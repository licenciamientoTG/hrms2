from django.urls import path
from .views import survey_dashboard_admin, survey_dashboard_user, survey_dashboard

urlpatterns = [
    path('', survey_dashboard,   name='survey_dashboard'),
    path('admin/', survey_dashboard_admin, name='survey_dashboard_admin'),
    path('user/', survey_dashboard_user, name='survey_dashboard_user'),
]
