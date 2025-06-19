from django.urls import path
from .views import document_dashboard_view

urlpatterns = [
    path('', document_dashboard_view, name='document_dashboard'),
]
