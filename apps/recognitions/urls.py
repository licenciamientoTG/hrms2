from django.urls import path
from .views import recognition_dashboard_view

urlpatterns = [
    path('', recognition_dashboard_view, name='recognition_dashboard'),
]
