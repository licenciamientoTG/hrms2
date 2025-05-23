from django.urls import path
from .views import archive_dashboard_view

urlpatterns = [
    path('', archive_dashboard_view, name='archive_dashboard'),
]
