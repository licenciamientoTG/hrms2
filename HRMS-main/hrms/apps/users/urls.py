from django.urls import path
from .views import user_dashboard_view

urlpatterns = [
    path('', user_dashboard_view, name='user_dashboard'),
]
